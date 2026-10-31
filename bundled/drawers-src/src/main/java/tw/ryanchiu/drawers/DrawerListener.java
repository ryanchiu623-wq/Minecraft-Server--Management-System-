package tw.ryanchiu.drawers;

import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.World;
import org.bukkit.block.Barrel;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.event.Event;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.block.Action;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockBurnEvent;
import org.bukkit.event.block.BlockExplodeEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.entity.EntityExplodeEvent;
import org.bukkit.event.inventory.InventoryMoveItemEvent;
import org.bukkit.event.inventory.InventoryOpenEvent;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.event.player.PlayerJoinEvent;
import org.bukkit.event.player.PlayerQuitEvent;
import org.bukkit.event.world.EntitiesLoadEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Vector;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;

/**
 * Everything players and hoppers do to drawers.
 *
 * Only the front face is a drawer; the other faces behave like any block,
 * except that the barrel's own inventory never opens.
 */
final class DrawerListener implements Listener {

    /** Two right-clicks closer than this are a double-click: deposit everything. */
    private static final long DOUBLE_CLICK_MS = 400;

    private record Click(Block block, long time) {
    }

    private record Punch(Block block, int tick) {
    }

    private final RyanDrawers plugin;
    private final Drawers drawers;
    private final DrawerMenu menu;
    private final Map<UUID, Click> lastClick = new HashMap<>();
    private final Map<UUID, Punch> lastPunch = new HashMap<>();

    DrawerListener(RyanDrawers plugin, Drawers drawers, DrawerMenu menu) {
        this.plugin = plugin;
        this.drawers = drawers;
        this.menu = menu;
    }

    // MONITOR: the placement can no longer be cancelled by anyone after this.
    @EventHandler(priority = EventPriority.MONITOR, ignoreCancelled = true)
    public void onPlace(BlockPlaceEvent event) {
        ItemStack hand = event.getItemInHand();
        if (!Items.isDrawer(hand) || event.getBlockPlaced().getType() != Material.BARREL) {
            return;
        }
        DrawerData d = DrawerData.read(hand.getItemMeta().getPersistentDataContainer());
        // Drawers face sideways, toward whoever placed them.
        drawers.create(event.getBlockPlaced(), event.getPlayer().getFacing().getOppositeFace(), d);
    }

    @EventHandler(priority = EventPriority.HIGH)
    public void onInteract(PlayerInteractEvent event) {
        Block block = event.getClickedBlock();
        if (block == null || event.useInteractedBlock() == Event.Result.DENY || !DrawerData.isDrawer(block)) {
            return;
        }
        BlockFace face = Displays.facing(block);
        if (event.getBlockFace() != face) {
            return;
        }
        Player player = event.getPlayer();
        if (event.getAction() == Action.RIGHT_CLICK_BLOCK) {
            event.setCancelled(true);
            if (event.getHand() == EquipmentSlot.HAND) {
                rightClick(player, block, face, event.getInteractionPoint() != null
                        ? event.getInteractionPoint().toVector() : aim(player, block));
            }
        } else if (event.getAction() == Action.LEFT_CLICK_BLOCK) {
            // Not cancelled: mining from the front still works, it just
            // takes items with the first hit (see onBreak). A hit that took
            // nothing is just mining, so an empty drawer breaks like any block.
            if (leftClick(player, block, face, aim(player, block))) {
                lastPunch.put(player.getUniqueId(), new Punch(block, Bukkit.getCurrentTick()));
            }
        }
    }

    private void rightClick(Player player, Block block, BlockFace face, Vector hit) {
        ItemStack hand = player.getInventory().getItemInMainHand();
        long now = System.currentTimeMillis();
        Click previous = lastClick.put(player.getUniqueId(), new Click(block, now));
        boolean twice = previous != null && previous.block().equals(block) && now - previous.time() < DOUBLE_CLICK_MS;

        int tier = Items.upgradeTier(hand);
        if (player.isSneaking() && hand.isEmpty()) {
            menu.open(player, block);
            return;
        }

        Barrel state = (Barrel) block.getState();
        DrawerData d = DrawerData.load(state);
        int slot = Displays.slotAt(block, face, hit, d.slots);

        if (tier > 0) {
            if (d.upgrades.size() >= RyanDrawers.settings().maxUpgrades()) {
                player.sendActionBar(Component.text("升級格滿了", NamedTextColor.RED));
                return;
            }
            d.upgrades.add(tier);
            hand.setAmount(hand.getAmount() - 1);
            player.sendActionBar(Component.text("容量變成 ×" + d.multiplier(), NamedTextColor.AQUA));
        } else if (twice && (hand.isEmpty() || d.matchSlot(hand) >= 0)) {
            // A quick second click holding something new is just another
            // insert, not a request to empty the inventory into the drawer.
            depositAll(player.getInventory(), d);
        } else if (!hand.isEmpty()) {
            long n = d.insert(hand, hand.getAmount(), slot);
            if (n == 0) {
                player.sendActionBar(Component.text(d.matchSlot(hand) >= 0 ? "這格滿了" : "放不下這個東西",
                        NamedTextColor.RED));
            }
            hand.setAmount(hand.getAmount() - (int) n);
        } else if (d.templates[slot] != null) {
            player.sendActionBar(Component.empty().append(d.templates[slot].effectiveName())
                    .append(Component.text("：" + d.counts[slot] + " / " + d.capacity(slot))));
        }
        drawers.save(block, state, d);
    }

    /** Puts every inventory item the drawer already holds into it. */
    private static void depositAll(PlayerInventory inv, DrawerData d) {
        ItemStack[] contents = inv.getStorageContents();
        for (int i = 0; i < contents.length; i++) {
            ItemStack item = contents[i];
            if (item == null || item.isEmpty() || d.matchSlot(item) < 0) {
                continue;
            }
            long n = d.insert(item, item.getAmount(), -1);
            if (n > 0) {
                item.setAmount(item.getAmount() - (int) n);
                inv.setItem(i, item.getAmount() > 0 ? item : null);
            }
        }
    }

    /** Takes a stack (sneaking: one) from the slot hit; true if anything came out. */
    private boolean leftClick(Player player, Block block, BlockFace face, Vector hit) {
        Barrel state = (Barrel) block.getState();
        DrawerData d = DrawerData.load(state);
        int slot = Displays.slotAt(block, face, hit, d.slots);
        if (d.templates[slot] == null) {
            return false;
        }
        ItemStack out = d.take(slot, player.isSneaking() ? 1 : d.templates[slot].getMaxStackSize());
        drawers.save(block, state, d);
        if (out != null) {
            Drawers.give(player, out);
        }
        return out != null;
    }

    /** Where the player is looking on the block. Left-clicks carry no hit point of their own. */
    private static Vector aim(Player player, Block block) {
        RayTraceResult r = player.rayTraceBlocks(6);
        return r != null && block.equals(r.getHitBlock()) ? r.getHitPosition() : null;
    }

    @EventHandler(priority = EventPriority.HIGHEST, ignoreCancelled = true)
    public void onBreak(BlockBreakEvent event) {
        Block block = event.getBlock();
        if (!DrawerData.isDrawer(block)) {
            return;
        }
        Player player = event.getPlayer();
        // A front-face hit that took items and breaks the drawer in the same
        // tick is an instant break (creative, or a fast enough tool): that hit
        // was meant to take items, not to mine.
        Punch punch = lastPunch.get(player.getUniqueId());
        if (punch != null && punch.block().equals(block) && punch.tick() == Bukkit.getCurrentTick()) {
            event.setCancelled(true);
            return;
        }
        Barrel state = (Barrel) block.getState();
        DrawerData d = DrawerData.load(state);
        event.setDropItems(false);
        // The contents travel inside the drawer item, not as loose items.
        ((Barrel) block.getState(false)).getInventory().clear();
        drawers.displays().remove(block);
        World world = block.getWorld();
        if (!(player.getGameMode() == GameMode.CREATIVE && d.isBlank())) {
            world.dropItemNaturally(block.getLocation().add(0.5, 0.5, 0.5), Items.drawer(d));
        }
        for (ItemStack extra : d.overflow) {
            world.dropItemNaturally(block.getLocation().add(0.5, 0.5, 0.5), extra);
        }
    }

    // Explosions would scatter or destroy a drawer's whole contents.
    @EventHandler(ignoreCancelled = true)
    public void onEntityExplode(EntityExplodeEvent event) {
        event.blockList().removeIf(DrawerData::isDrawer);
    }

    @EventHandler(ignoreCancelled = true)
    public void onBlockExplode(BlockExplodeEvent event) {
        event.blockList().removeIf(DrawerData::isDrawer);
    }

    @EventHandler(ignoreCancelled = true)
    public void onBurn(BlockBurnEvent event) {
        if (DrawerData.isDrawer(event.getBlock())) {
            event.setCancelled(true);
        }
    }

    /** The barrel inventory is only the hopper buffer; players never see it. */
    @EventHandler(ignoreCancelled = true)
    public void onOpen(InventoryOpenEvent event) {
        if (event.getInventory().getHolder(false) instanceof Barrel barrel
                && DrawerData.isDrawer(barrel.getPersistentDataContainer())) {
            event.setCancelled(true);
        }
    }

    @EventHandler(priority = EventPriority.HIGH, ignoreCancelled = true)
    public void onHopper(InventoryMoveItemEvent event) {
        Inventory dest = event.getDestination();
        if (dest.getHolder(false) instanceof Barrel barrel
                && DrawerData.isDrawer(barrel.getPersistentDataContainer())) {
            DrawerData d = DrawerData.load(barrel.getPersistentDataContainer(), dest);
            ItemStack item = event.getItem();
            if (d.room(item) < item.getAmount()) {
                event.setCancelled(true);
                return;
            }
            drawers.syncLater(barrel.getBlock());
        }
        if (event.getSource().getHolder(false) instanceof Barrel barrel
                && DrawerData.isDrawer(barrel.getPersistentDataContainer())) {
            drawers.syncLater(barrel.getBlock());
        }
    }

    /** Displays whose drawer is gone (WorldEdit, /setblock...) go too. */
    @EventHandler
    public void onEntitiesLoad(EntitiesLoadEvent event) {
        for (Entity e : event.getEntities()) {
            if (!Displays.isOurs(e)) {
                continue;
            }
            String[] xyz = e.getPersistentDataContainer().get(Keys.OWNER, PersistentDataType.STRING).split(",");
            if (xyz.length != 3) {
                e.remove();
                continue;
            }
            int x = Integer.parseInt(xyz[0]);
            int y = Integer.parseInt(xyz[1]);
            int z = Integer.parseInt(xyz[2]);
            World world = e.getWorld();
            if (world.isChunkLoaded(x >> 4, z >> 4) && !DrawerData.isDrawer(world.getBlockAt(x, y, z))) {
                e.remove();
            }
        }
    }

    @EventHandler
    public void onJoin(PlayerJoinEvent event) {
        for (NamespacedKey key : plugin.recipeKeys()) {
            event.getPlayer().discoverRecipe(key);
        }
    }

    @EventHandler
    public void onQuit(PlayerQuitEvent event) {
        lastClick.remove(event.getPlayer().getUniqueId());
        lastPunch.remove(event.getPlayer().getUniqueId());
    }
}
