package tw.ryanchiu.drawers;

import java.util.List;

import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.block.Barrel;
import org.bukkit.block.Block;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryDragEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryHolder;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;

/**
 * Sneak + right-click with an empty hand: the drawer's upgrades and lock.
 *
 * Every click is cancelled and carried out here instead, so nothing can be
 * dragged in or out behind the drawer's back: click an installed upgrade to
 * take it out, click an upgrade in your own inventory to put it in, click the
 * hook to lock or unlock.
 */
final class DrawerMenu implements Listener {

    private static final int LOCK_SLOT = 8;
    private static final int INFO_SLOT = 7;

    /** Ties an open menu to its drawer. */
    private static final class Holder implements InventoryHolder {
        final Block block;
        Inventory inventory;

        Holder(Block block) {
            this.block = block;
        }

        @Override
        public Inventory getInventory() {
            return inventory;
        }
    }

    private final Drawers drawers;

    DrawerMenu(Drawers drawers) {
        this.drawers = drawers;
    }

    void open(Player player, Block block) {
        Holder holder = new Holder(block);
        holder.inventory = Bukkit.createInventory(holder, 9, Component.text("抽屜設定", NamedTextColor.DARK_GRAY));
        render(holder, DrawerData.load((Barrel) block.getState()));
        player.openInventory(holder.inventory);
    }

    private void render(Holder holder, DrawerData d) {
        Inventory inv = holder.inventory;
        inv.clear();
        int max = RyanDrawers.settings().maxUpgrades();
        for (int i = 0; i < max && i < INFO_SLOT; i++) {
            if (i < d.upgrades.size()) {
                ItemStack up = Items.upgrade(d.upgrades.get(i));
                ItemMeta meta = up.getItemMeta();
                meta.lore(List.of(Items.plain("點一下拆下來", NamedTextColor.YELLOW)));
                up.setItemMeta(meta);
                inv.setItem(i, up);
            } else {
                inv.setItem(i, button(Material.LIGHT_GRAY_STAINED_GLASS_PANE, "空的升級格",
                        NamedTextColor.GRAY, "點背包裡的儲存升級裝上"));
            }
        }
        inv.setItem(INFO_SLOT, button(Material.BOOK, Items.layoutName(d.slots), NamedTextColor.YELLOW,
                "容量 ×" + d.multiplier() + "，每格最多 " + d.capacityFor(null, d.multiplier()) + " 個（以 64 一組計）"));
        inv.setItem(LOCK_SLOT, d.locked
                ? button(Material.TRIPWIRE_HOOK, "已鎖定（點一下解鎖）", NamedTextColor.GOLD,
                        "清空的格子也會記住原本放的東西")
                : button(Material.TRIPWIRE_HOOK, "未鎖定（點一下鎖定）", NamedTextColor.GRAY,
                        "鎖定後，清空的格子會記住原本放的東西"));
    }

    private static ItemStack button(Material type, String name, NamedTextColor color, String lore) {
        ItemStack item = new ItemStack(type);
        ItemMeta meta = item.getItemMeta();
        meta.displayName(Items.plain(name, color));
        meta.lore(List.of(Items.plain(lore, NamedTextColor.GRAY)));
        item.setItemMeta(meta);
        return item;
    }

    @EventHandler
    public void onClick(InventoryClickEvent event) {
        if (!(event.getView().getTopInventory().getHolder(false) instanceof Holder holder)) {
            return;
        }
        event.setCancelled(true);
        if (!(event.getWhoClicked() instanceof Player player)) {
            return;
        }
        Block block = holder.block;
        if (!DrawerData.isDrawer(block)) {
            player.closeInventory();
            return;
        }
        Barrel state = (Barrel) block.getState();
        DrawerData d = DrawerData.load(state);
        boolean top = event.getClickedInventory() == event.getView().getTopInventory();

        if (top && event.getSlot() == LOCK_SLOT) {
            d.locked = !d.locked;
            d.forgetEmpty();
        } else if (top && event.getSlot() < d.upgrades.size()) {
            int index = event.getSlot();
            if (!d.fitsWithMultiplier(d.multiplierWithout(index))) {
                player.sendMessage(Component.text("拆掉這個升級就放不下了，先拿一些東西出來。", NamedTextColor.RED));
                return;
            }
            int tier = d.upgrades.remove(index);
            Drawers.give(player, Items.upgrade(tier));
        } else if (!top && event.getClickedInventory() != null) {
            ItemStack clicked = event.getCurrentItem();
            int tier = Items.upgradeTier(clicked);
            if (tier == 0) {
                return;
            }
            if (d.upgrades.size() >= RyanDrawers.settings().maxUpgrades()) {
                player.sendMessage(Component.text("升級格滿了。", NamedTextColor.RED));
                return;
            }
            d.upgrades.add(tier);
            clicked.setAmount(clicked.getAmount() - 1);
            event.setCurrentItem(clicked.getAmount() > 0 ? clicked : null);
        } else {
            return;
        }
        drawers.save(block, state, d);
        render(holder, d);
    }

    @EventHandler
    public void onDrag(InventoryDragEvent event) {
        if (event.getView().getTopInventory().getHolder(false) instanceof Holder) {
            event.setCancelled(true);
        }
    }
}
