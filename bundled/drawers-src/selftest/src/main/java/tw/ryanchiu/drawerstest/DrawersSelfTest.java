package tw.ryanchiu.drawerstest;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Deque;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;

import org.bukkit.Bukkit;
import org.bukkit.Chunk;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.World;
import org.bukkit.block.Barrel;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.BlockState;
import org.bukkit.block.data.Directional;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.enchantments.Enchantment;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Item;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.TNTPrimed;
import org.bukkit.entity.TextDisplay;
import org.bukkit.event.Event;
import org.bukkit.event.EventException;
import org.bukkit.event.block.Action;
import org.bukkit.event.block.BlockBreakEvent;
import org.bukkit.event.block.BlockBurnEvent;
import org.bukkit.event.block.BlockPlaceEvent;
import org.bukkit.event.inventory.ClickType;
import org.bukkit.event.inventory.InventoryAction;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.event.inventory.InventoryOpenEvent;
import org.bukkit.event.inventory.InventoryType;
import org.bukkit.event.player.PlayerInteractEvent;
import org.bukkit.inventory.EquipmentSlot;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.plugin.Plugin;
import org.bukkit.plugin.RegisteredListener;
import org.bukkit.plugin.java.JavaPlugin;
import org.bukkit.util.BoundingBox;
import org.bukkit.util.RayTraceResult;
import org.bukkit.util.Vector;

import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;

/**
 * Test-server only: drives RyanDrawers the way a player would - clicks on
 * the front, double-clicks, punches, breaking, placing, the settings menu -
 * by handing real events to RyanDrawers' own listeners, then checks the
 * drawer's stored data, its displays and the fake player's inventory.
 *
 * Only RyanDrawers' listeners receive the events, so other plugins never see
 * the fake player. Results go to the server log as PASS / FAIL lines.
 */
public final class DrawersSelfTest extends JavaPlugin {

    private static final int Y = -60;
    private static final int Z = 26;
    private static final String NS = "ryandrawers";
    private static final NamespacedKey SLOTS = new NamespacedKey(NS, "slots");
    private static final NamespacedKey ITEMS = new NamespacedKey(NS, "items");
    private static final NamespacedKey COUNTS = new NamespacedKey(NS, "counts");
    private static final NamespacedKey LOCKED = new NamespacedKey(NS, "locked");
    private static final NamespacedKey UPGRADES = new NamespacedKey(NS, "upgrades");
    private static final NamespacedKey UPGRADE = new NamespacedKey(NS, "upgrade");
    private static final NamespacedKey OWNER = new NamespacedKey(NS, "owner");
    private static final NamespacedKey ROLE = new NamespacedKey(NS, "role");
    private static final Material[] TIER_MATERIALS = {
            Material.OBSIDIAN, Material.IRON_INGOT, Material.GOLD_INGOT, Material.DIAMOND, Material.EMERALD};
    /** Top-left, top-right, bottom-left, bottom-right as seen from in front: the quad drawer's slots 0-3. */
    private static final double[][] QUADRANTS = {{-0.25, 0.25}, {0.25, 0.25}, {-0.25, -0.25}, {0.25, -0.25}};
    private static final int CLICK_GAP = 10; // ticks: well past the 400 ms double-click window

    private record Step(int delay, String name, Runnable body) {
    }

    /** A drawer's full contents: persistent data plus the barrel's stock, as the plugin counts them. */
    private record Contents(ItemStack[] templates, long[] counts, boolean locked, List<Integer> upgrades) {
        Material type(int slot) {
            return templates[slot] == null ? null : templates[slot].getType();
        }

        long total() {
            long n = 0;
            for (long c : counts) {
                n += c;
            }
            return n;
        }
    }

    private final Deque<Step> steps = new ArrayDeque<>();
    private final List<String> failures = new ArrayList<>();
    private final List<FakePlayer> players = new ArrayList<>();
    private Plugin drawers;
    private World world;
    private int passed;
    private boolean running;

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (running) {
            sender.sendMessage("自動測試還在跑。");
            return true;
        }
        drawers = getServer().getPluginManager().getPlugin("RyanDrawers");
        if (drawers == null || !drawers.isEnabled()) {
            sender.sendMessage("RyanDrawers 沒有啟用。");
            return true;
        }
        world = getServer().getWorlds().get(0);
        passed = 0;
        failures.clear();
        players.clear();
        steps.clear();
        buildSteps();
        running = true;
        getLogger().info("=== RyanDrawers 自動測試開始：" + steps.size() + " 個步驟 ===");
        next();
        sender.sendMessage("自動測試開始，結果寫在伺服器日誌。");
        return true;
    }

    private void step(int delay, String name, Runnable body) {
        steps.add(new Step(delay, name, body));
    }

    private void next() {
        Step s = steps.poll();
        if (s == null) {
            finish();
            return;
        }
        getServer().getScheduler().runTaskLater(this, () -> {
            getLogger().info("-- " + s.name());
            try {
                s.body().run();
            } catch (Throwable t) {
                fail(s.name() + " 丟出例外：" + t);
                getLogger().log(java.util.logging.Level.WARNING, "例外", t);
            }
            next();
        }, Math.max(1, s.delay()));
    }

    private void finish() {
        running = false;
        Set<String> unhandled = new TreeSet<>();
        for (FakePlayer p : players) {
            unhandled.addAll(p.unhandled);
        }
        for (int cx = 0; cx <= 4; cx++) {
            world.removePluginChunkTicket(cx, 1, this);
        }
        if (!unhandled.isEmpty()) {
            getLogger().info("假玩家沒有實作、回傳預設值的方法：" + unhandled);
        }
        getLogger().info("=== 結果：通過 " + passed + "，失敗 " + failures.size() + " ===");
        for (String f : failures) {
            getLogger().warning("  失敗：" + f);
        }
    }

    // ------------------------------------------------------------------ checks

    private void check(boolean ok, String what) {
        if (ok) {
            passed++;
            getLogger().info("PASS " + what);
        } else {
            fail(what);
        }
    }

    private void fail(String what) {
        failures.add(what);
        getLogger().warning("FAIL " + what);
    }

    private void eq(Object expected, Object actual, String what) {
        check(java.util.Objects.equals(expected, actual), what + "（預期 " + expected + "，實際 " + actual + "）");
    }

    private void eq(long expected, long actual, String what) {
        check(expected == actual, what + "（預期 " + expected + "，實際 " + actual + "）");
    }

    // ----------------------------------------------------------------- helpers

    private Block block(int x) {
        return world.getBlockAt(x, Y, Z);
    }

    private void place(Block b, int slots, BlockFace f) {
        getServer().dispatchCommand(getServer().getConsoleSender(), "drawers place " + world.getName() + " "
                + b.getX() + " " + b.getY() + " " + b.getZ() + " " + slots + " " + f.name().toLowerCase(Locale.ROOT));
    }

    /** A fake player standing a block and a half in front of the face, looking at it. */
    private FakePlayer playerFacing(Block b, BlockFace f) {
        Vector n = f.getDirection();
        Location loc = b.getLocation().add(0.5, 0, 0.5).add(n.clone().multiply(1.5));
        loc.setDirection(n.clone().multiply(-1));
        FakePlayer p = new FakePlayer(loc, getClassLoader());
        players.add(p);
        return p;
    }

    /** The viewer's right, worked out from the look direction rather than taken from the plugin. */
    private static Vector viewerRight(BlockFace f) {
        return f.getDirection().multiply(-1).crossProduct(new Vector(0, 1, 0));
    }

    /** A point on the face, relative to the block corner: u to the viewer's right, v up. */
    private static Vector facePoint(BlockFace f, double u, double v) {
        Vector p = new Vector(0.5, 0.5, 0.5).add(f.getDirection().multiply(0.5));
        if (f.getModY() == 0) {
            p.add(viewerRight(f).multiply(u)).add(new Vector(0, v, 0));
        }
        return p;
    }

    /** Where an entity sits relative to the face: {right, up, out}. */
    private static double[] uvn(Block b, BlockFace f, Location loc) {
        Vector rel = loc.toVector().subtract(b.getLocation().toVector().add(new Vector(0.5, 0.5, 0.5)));
        return new double[] {rel.dot(viewerRight(f)), rel.getY(), rel.dot(f.getDirection())};
    }

    private static float faceYaw(BlockFace f) {
        return switch (f) {
            case SOUTH -> 0;
            case WEST -> 90;
            case NORTH -> 180;
            default -> 270;
        };
    }

    private void yaw(BlockFace f, Entity e, String what) {
        float actual = ((e.getLocation().getYaw() % 360) + 360) % 360;
        float diff = Math.abs(actual - faceYaw(f)) % 360;
        check(Math.min(diff, 360 - diff) < 0.5, what + "（預期 yaw " + faceYaw(f) + "，實際 " + actual + "）");
    }

    private void fire(Event e) {
        for (RegisteredListener rl : e.getHandlers().getRegisteredListeners()) {
            if (rl.getPlugin() == drawers) {
                try {
                    rl.callEvent(e);
                } catch (EventException ex) {
                    throw new IllegalStateException(ex.getCause() != null ? ex.getCause() : ex);
                }
            }
        }
    }

    private PlayerInteractEvent rightClick(FakePlayer p, Block b, BlockFace face, double u, double v) {
        ItemStack hand = p.hand();
        PlayerInteractEvent e = new PlayerInteractEvent(p.player, Action.RIGHT_CLICK_BLOCK,
                hand.isEmpty() ? null : hand, b, face, EquipmentSlot.HAND, facePoint(face, u, v));
        fire(e);
        return e;
    }

    private void leftClick(FakePlayer p, Block b, BlockFace face, double u, double v) {
        p.aim = new RayTraceResult(b.getLocation().toVector().add(facePoint(face, u, v)), b, face);
        ItemStack hand = p.hand();
        fire(new PlayerInteractEvent(p.player, Action.LEFT_CLICK_BLOCK, hand.isEmpty() ? null : hand, b, face,
                EquipmentSlot.HAND));
    }

    private void menuClick(FakePlayer p, boolean top, int index) {
        Inventory menu = p.opened;
        int raw = top ? index : menu.getSize() + index;
        fire(new InventoryClickEvent(p.view(menu), InventoryType.SlotType.CONTAINER, raw, ClickType.LEFT,
                InventoryAction.PICKUP_ALL));
    }

    private Contents contents(Block b) {
        if (b.getType() != Material.BARREL) {
            return null;
        }
        Barrel barrel = (Barrel) b.getState();
        PersistentDataContainer pdc = barrel.getPersistentDataContainer();
        Integer slots = pdc.get(SLOTS, PersistentDataType.INTEGER);
        if (slots == null) {
            return null;
        }
        Contents c = read(pdc);
        for (ItemStack item : barrel.getSnapshotInventory().getContents()) {
            if (item == null || item.isEmpty()) {
                continue;
            }
            int s = -1;
            for (int i = 0; i < slots && s < 0; i++) {
                if (c.templates[i] != null && c.templates[i].isSimilar(item)) {
                    s = i;
                }
            }
            for (int i = 0; i < slots && s < 0; i++) {
                if (c.templates[i] == null) {
                    s = i;
                }
            }
            if (s < 0) {
                fail(b.getX() + "," + b.getZ() + " 木桶裡有放不進任何一格的東西：" + item);
                continue;
            }
            if (c.templates[s] == null) {
                c.templates[s] = item.asOne();
            }
            c.counts[s] += item.getAmount();
        }
        return c;
    }

    /** Drawer data as stored in a persistent data container (block or item). */
    private static Contents read(PersistentDataContainer pdc) {
        int slots = pdc.getOrDefault(SLOTS, PersistentDataType.INTEGER, 1);
        ItemStack[] templates = new ItemStack[slots];
        long[] counts = new long[slots];
        List<byte[]> items = pdc.get(ITEMS, PersistentDataType.LIST.byteArrays());
        long[] stored = pdc.get(COUNTS, PersistentDataType.LONG_ARRAY);
        for (int i = 0; i < slots; i++) {
            if (items != null && i < items.size() && items.get(i).length > 0) {
                templates[i] = ItemStack.deserializeBytes(items.get(i));
            }
            if (stored != null && i < stored.length) {
                counts[i] = stored[i];
            }
        }
        List<Integer> ups = new ArrayList<>();
        int[] u = pdc.get(UPGRADES, PersistentDataType.INTEGER_ARRAY);
        if (u != null) {
            for (int t : u) {
                ups.add(t);
            }
        }
        return new Contents(templates, counts, pdc.getOrDefault(LOCKED, PersistentDataType.BOOLEAN, false), ups);
    }

    private Map<String, Display> displays(Block b) {
        String key = b.getX() + "," + b.getY() + "," + b.getZ();
        Map<String, Display> found = new HashMap<>();
        for (Entity e : world.getNearbyEntities(BoundingBox.of(b).expand(0.5), e -> e instanceof Display)) {
            PersistentDataContainer pdc = e.getPersistentDataContainer();
            if (key.equals(pdc.get(OWNER, PersistentDataType.STRING))) {
                found.put(pdc.get(ROLE, PersistentDataType.STRING), (Display) e);
            }
        }
        return found;
    }

    private int displayCount(String ownerKey, BoundingBox box) {
        return world.getNearbyEntities(box, e -> e instanceof Display
                && ownerKey.equals(e.getPersistentDataContainer().get(OWNER, PersistentDataType.STRING))).size();
    }

    private static String text(Display d) {
        return d instanceof TextDisplay t ? PlainTextComponentSerializer.plainText().serialize(t.text()) : null;
    }

    private List<Item> drops(Block b) {
        return world.getNearbyEntities(BoundingBox.of(b).expand(2), e -> e instanceof Item).stream()
                .map(e -> (Item) e).toList();
    }

    private static int count(Inventory inv, Material m) {
        int n = 0;
        for (ItemStack s : inv.getContents()) {
            if (s != null && s.getType() == m) {
                n += s.getAmount();
            }
        }
        return n;
    }

    private ItemStack craft(Material... grid) {
        ItemStack[] matrix = new ItemStack[9];
        for (int i = 0; i < 9; i++) {
            matrix[i] = grid[i] == null ? null : new ItemStack(grid[i]);
        }
        return Bukkit.craftItemResult(matrix, world).getResult();
    }

    private ItemStack upgradeItem(int tier) {
        Material m = TIER_MATERIALS[tier - 1];
        Material s = Material.STICK;
        return craft(m, s, m, s, Material.CHEST, s, m, s, m);
    }

    private static int tierOf(ItemStack item) {
        if (item == null || !item.hasItemMeta()) {
            return 0;
        }
        return item.getItemMeta().getPersistentDataContainer().getOrDefault(UPGRADE, PersistentDataType.INTEGER, 0);
    }

    private BlockBreakEvent breakBlock(FakePlayer p, Block b) {
        BlockBreakEvent e = new BlockBreakEvent(b, p.player);
        fire(e);
        return e;
    }

    // ------------------------------------------------------------------- tests

    private void buildSteps() {
        step(1, "準備場地", this::prepare);
        orientation();
        basics();
        breakAndPlace();
        creativeAndCrafting();
        creativeFront();
        explosions();
        misc();
        buying();
        orphans();
    }

    private void prepare() {
        for (int cx = 0; cx <= 4; cx++) {
            world.addPluginChunkTicket(cx, 1, this);
        }
        for (int x = 14; x <= 75; x++) {
            for (int z = 18; z <= 34; z++) {
                for (int y = Y; y <= Y + 5; y++) {
                    Block b = world.getBlockAt(x, y, z);
                    if (b.getState(false) instanceof Barrel barrel) {
                        barrel.getInventory().clear();
                    }
                    if (!b.getType().isAir()) {
                        b.setType(Material.AIR, false);
                    }
                }
                world.getBlockAt(x, Y - 1, z).setType(Material.GRASS_BLOCK, false);
                world.getBlockAt(x, Y - 2, z).setType(Material.DIRT, false);
                world.getBlockAt(x, Y - 3, z).setType(Material.DIRT, false);
            }
        }
        BoundingBox area = new BoundingBox(14, Y - 4, 18, 76, Y + 8, 35);
        for (Entity e : world.getNearbyEntities(area, e -> e instanceof Item || e instanceof TNTPrimed
                || (e instanceof Display && e.getPersistentDataContainer().has(OWNER)))) {
            e.remove();
        }
        Block orphan = world.getBlockAt(200, Y, 200);
        world.getChunkAt(orphan).load();
        orphan.setType(Material.AIR, false);
        check(true, "場地清好了");
    }

    /** All four facings: each quadrant clicked lands in the slot drawn there, and the icons face out. */
    private void orientation() {
        BlockFace[] faces = {BlockFace.NORTH, BlockFace.SOUTH, BlockFace.EAST, BlockFace.WEST};
        Material[] mats = {Material.STONE, Material.DIRT, Material.SAND, Material.OAK_LOG};
        String[] names = {"左上", "右上", "左下", "右下"};
        for (int i = 0; i < faces.length; i++) {
            BlockFace f = faces[i];
            Block b = block(18 + 3 * i);
            FakePlayer[] p = new FakePlayer[1];
            step(1, "方向 " + f + "：放四格抽屜", () -> {
                place(b, 4, f);
                p[0] = playerFacing(b, f);
                eq(f, ((Directional) b.getBlockData()).getFacing(), f + " 抽屜朝向");
            });
            for (int k = 0; k < 4; k++) {
                int q = k;
                step(CLICK_GAP, "方向 " + f + "：對" + names[q] + "按右鍵放 " + mats[q], () -> {
                    p[0].storage.setItem(0, new ItemStack(mats[q], 64));
                    PlayerInteractEvent e = rightClick(p[0], b, f, QUADRANTS[q][0], QUADRANTS[q][1]);
                    check(e.useInteractedBlock() == Event.Result.DENY, f + " " + names[q] + " 右鍵有被取消（不會開木桶）");
                    check(p[0].hand().isEmpty(), f + " " + names[q] + " 手上的 64 個都放進去了");
                });
            }
            step(1, "方向 " + f + "：檢查格子和顯示位置", () -> {
                Contents c = contents(b);
                Map<String, Display> ds = displays(b);
                for (int q = 0; q < 4; q++) {
                    eq(mats[q], c.type(q), f + " 第 " + q + " 格（" + names[q] + "）的東西");
                    eq(64, c.counts[q], f + " 第 " + q + " 格數量");
                    Display icon = ds.get("icon" + q);
                    if (!(icon instanceof ItemDisplay id)) {
                        fail(f + " 第 " + q + " 格沒有圖示");
                        continue;
                    }
                    eq(mats[q], id.getItemStack().getType(), f + " 第 " + q + " 格圖示畫的東西");
                    double[] at = uvn(b, f, icon.getLocation());
                    check(Math.signum(at[0]) == Math.signum(QUADRANTS[q][0])
                                    && Math.signum(at[1]) == Math.signum(QUADRANTS[q][1]),
                            f + " " + mats[q] + " 的圖示畫在" + names[q] + "（右 " + fmt(at[0]) + "，上 " + fmt(at[1]) + "）");
                    check(at[2] > 0.5 && at[2] < 0.56, f + " 圖示貼在正面外側（離中心 " + fmt(at[2]) + "）");
                    yaw(f, icon, f + " 圖示面向");
                    Display count = ds.get("count" + q);
                    eq("64", count == null ? null : text(count), f + " 第 " + q + " 格數字");
                    if (count != null) {
                        double[] ct = uvn(b, f, count.getLocation());
                        check(Math.signum(ct[0]) == Math.signum(QUADRANTS[q][0]) && ct[1] < at[1],
                                f + " 第 " + q + " 格數字在圖示正下方");
                        yaw(f, count, f + " 數字面向");
                    }
                }
            });
            step(1, "方向 " + f + "：左鍵右上、蹲下左鍵左下", () -> {
                leftClick(p[0], b, f, 0.25, 0.25);
                eq(64, count(p[0].storage, Material.DIRT), f + " 左鍵右上拿到一組泥土");
                Contents c = contents(b);
                eq(null, c.type(1), f + " 右上拿空後（沒鎖）忘記放的東西");
                check(!displays(b).containsKey("icon1"), f + " 右上拿空後圖示消失");
                p[0].sneaking = true;
                leftClick(p[0], b, f, -0.25, -0.25);
                p[0].sneaking = false;
                eq(1, count(p[0].storage, Material.SAND), f + " 蹲下左鍵左下拿到 1 個沙");
                eq(63, contents(b).counts[2], f + " 左下剩 63 個沙");
            });
        }
    }

    /** One single drawer: insert, refuse, double-click, full, take, upgrade, menu, lock. */
    private void basics() {
        Block b = block(33);
        BlockFace f = BlockFace.SOUTH;
        FakePlayer[] p = new FakePlayer[1];
        step(1, "單格：右鍵放入、放錯東西", () -> {
            place(b, 1, f);
            p[0] = playerFacing(b, f);
            p[0].storage.setItem(0, new ItemStack(Material.COBBLESTONE, 64));
            rightClick(p[0], b, f, 0, 0);
            eq(64, contents(b).counts[0], "單格 右鍵放進 64 個鵝卵石");
        });
        step(CLICK_GAP, "單格：放錯東西", () -> {
            p[0].storage.setItem(0, new ItemStack(Material.DIRT, 64));
            rightClick(p[0], b, f, 0, 0);
            eq(64, contents(b).counts[0], "單格 拿泥土右鍵不會放進去");
            eq(64, p[0].hand().getAmount(), "單格 泥土還在手上");
            check(p[0].lastActionBar().contains("放不下"), "單格 提示「放不下這個東西」（實際：" + p[0].lastActionBar() + "）");
        });
        step(CLICK_GAP, "單格：連點兩下把背包裡的全放進去，放到滿為止", () -> {
            p[0].storage.clear();
            for (int i = 0; i < 35; i++) {
                p[0].storage.setItem(i, new ItemStack(Material.COBBLESTONE, 64));
            }
            p[0].storage.setItem(35, new ItemStack(Material.DIRT, 64));
            rightClick(p[0], b, f, 0, 0);
            rightClick(p[0], b, f, 0, 0);
            eq(2048, contents(b).counts[0], "單格 連點後裝到上限 2048");
            eq(35 * 64 - 64 - 1920, count(p[0].storage, Material.COBBLESTONE), "單格 背包剩下放不進去的鵝卵石");
            eq(64, count(p[0].storage, Material.DIRT), "單格 背包的泥土沒被動到");
        });
        step(CLICK_GAP, "單格：滿了再放", () -> {
            p[0].storage.setItem(0, new ItemStack(Material.COBBLESTONE, 64));
            rightClick(p[0], b, f, 0, 0);
            eq(64, p[0].hand().getAmount(), "單格 滿了之後手上的沒有少");
            check(p[0].lastActionBar().contains("滿了"), "單格 提示「這格滿了」（實際：" + p[0].lastActionBar() + "）");
            Display count = displays(b).get("count0");
            eq("2048", text(count), "單格 數字顯示 2048");
            check(count instanceof TextDisplay t && NamedTextColor.GOLD.equals(t.text().color()), "單格 滿了數字變金色");
        });
        step(1, "單格：左鍵拿一組、蹲下左鍵拿一個", () -> {
            p[0].storage.clear();
            leftClick(p[0], b, f, 0, 0);
            eq(64, count(p[0].storage, Material.COBBLESTONE), "單格 左鍵拿到 64 個");
            p[0].sneaking = true;
            leftClick(p[0], b, f, 0, 0);
            p[0].sneaking = false;
            eq(65, count(p[0].storage, Material.COBBLESTONE), "單格 蹲下左鍵再拿 1 個");
            eq(1983, contents(b).counts[0], "單格 剩 1983");
            eq("1983", text(displays(b).get("count0")), "單格 數字跟著變成 1983");
        });
        step(CLICK_GAP, "單格：拿升級右鍵裝上", () -> {
            ItemStack up = upgradeItem(2);
            eq(2, tierOf(up), "合成出來的是二級升級（鐵）");
            up.setAmount(2);
            p[0].storage.setItem(0, up);
            rightClick(p[0], b, f, 0, 0);
            eq(List.of(2), contents(b).upgrades(), "單格 裝上二級升級");
            eq(1, p[0].hand().getAmount(), "單格 升級用掉一個");
            check(p[0].lastActionBar().contains("×4"), "單格 提示容量 ×4（實際：" + p[0].lastActionBar() + "）");
        });
        step(CLICK_GAP, "單格：蹲下空手右鍵開設定、鎖定、拆裝升級", () -> {
            p[0].storage.clear();
            p[0].sneaking = true;
            rightClick(p[0], b, f, 0, 0);
            p[0].sneaking = false;
            Inventory menu = p[0].opened;
            check(menu != null && menu.getSize() == 9, "單格 打開 9 格的設定選單");
            if (menu == null) {
                return;
            }
            eq(2, tierOf(menu.getItem(0)), "選單第 1 格是裝上的升級");
            eq(Material.TRIPWIRE_HOOK, menu.getItem(8) == null ? null : menu.getItem(8).getType(), "選單最後一格是鎖");
            menuClick(p[0], true, 8);
            check(contents(b).locked(), "點鎖之後已鎖定");
            check(displays(b).containsKey("lock"), "鎖定後正面出現「鎖」字");
            menuClick(p[0], true, 0);
            eq(List.of(), contents(b).upgrades(), "點升級把它拆下來");
            eq(1, count(p[0].storage, Material.PAPER), "拆下的升級回到背包");
            eq(Material.LIGHT_GRAY_STAINED_GLASS_PANE, menu.getItem(0) == null ? null : menu.getItem(0).getType(),
                    "拆掉後選單那格變回空格");
            int slot = p[0].storage.first(Material.PAPER);
            menuClick(p[0], false, slot);
            eq(List.of(2), contents(b).upgrades(), "點背包裡的升級裝回去");
            eq(0, count(p[0].storage, Material.PAPER), "裝回去後背包的升級沒了");
            check(menu.getItem(0) != null && tierOf(menu.getItem(0)) == 2, "選單畫面跟著更新");
            p[0].storage.clear();
            for (int i = 0; i < 5; i++) {
                p[0].storage.setItem(i, new ItemStack(Material.COBBLESTONE, 64));
            }
        });
        step(CLICK_GAP, "單格：超過基本容量時不能拆升級", () -> {
            rightClick(p[0], b, f, 0, 0);
            rightClick(p[0], b, f, 0, 0);
            eq(1983 + 320, contents(b).counts[0], "單格 有升級可以放超過 2048");
            menuClick(p[0], true, 0);
            eq(List.of(2), contents(b).upgrades(), "東西太多時升級拆不下來");
            check(p[0].lastMessage().contains("放不下"), "提示先拿東西出來（實際：" + p[0].lastMessage() + "）");
        });
        step(1, "單格：鎖定時拿空會記住東西", () -> {
            for (int i = 0; i < 60 && contents(b).counts[0] > 0; i++) {
                p[0].storage.clear();
                leftClick(p[0], b, f, 0, 0);
            }
            Contents c = contents(b);
            eq(0, c.counts[0], "單格 全部拿出來");
            eq(Material.COBBLESTONE, c.type(0), "鎖定的空格還記得鵝卵石");
            check(displays(b).containsKey("icon0"), "鎖定的空格圖示還在");
            eq("0", text(displays(b).get("count0")), "空格數字顯示 0");
            p[0].storage.clear();
            p[0].storage.setItem(0, new ItemStack(Material.DIRT, 64));
        });
        step(CLICK_GAP, "單格：鎖定的空格不收別的東西", () -> {
            rightClick(p[0], b, f, 0, 0);
            eq(64, p[0].hand().getAmount(), "鎖定的空格不收泥土");
            eq(null, contents(b).type(0) == Material.DIRT ? Material.DIRT : null, "格子沒變成泥土");
            menuClick(p[0], true, 8);
            Contents c = contents(b);
            check(!c.locked(), "再點一次鎖就解鎖");
            eq(null, c.type(0), "解鎖後空格忘記放的東西");
            check(!displays(b).containsKey("icon0") && !displays(b).containsKey("lock"), "解鎖後圖示和「鎖」字消失");
        });
    }

    /** Breaking keeps everything in the item, placing it back restores it; front punches don't break. */
    private void breakAndPlace() {
        Block b = block(36);
        BlockFace f = BlockFace.SOUTH;
        FakePlayer[] p = new FakePlayer[1];
        ItemStack[] dropped = new ItemStack[1];
        step(1, "挖掉：準備一個有 500 個鵝卵石、升級、鎖定的抽屜", () -> {
            place(b, 1, f);
            p[0] = playerFacing(b, f);
            for (int i = 0; i < 7; i++) {
                p[0].storage.setItem(i, new ItemStack(Material.COBBLESTONE, 64));
            }
            p[0].storage.setItem(7, new ItemStack(Material.COBBLESTONE, 52));
            rightClick(p[0], b, f, 0, 0);
            rightClick(p[0], b, f, 0, 0);
            eq(500, contents(b).counts[0], "挖掉前有 500 個");
        });
        step(CLICK_GAP, "挖掉：裝升級、鎖定", () -> {
            p[0].storage.setItem(0, upgradeItem(1));
            rightClick(p[0], b, f, 0, 0);
            p[0].sneaking = true;
            rightClick(p[0], b, f, 0, 0);
            p[0].sneaking = false;
            menuClick(p[0], true, 8);
            Contents c = contents(b);
            check(c.locked() && c.upgrades().equals(List.of(1)), "挖掉前已鎖定、裝一級升級");
        });
        step(CLICK_GAP, "挖掉：從側面挖（生存）", () -> {
            BlockBreakEvent e = breakBlock(p[0], b);
            check(!e.isCancelled(), "生存模式從側面挖可以挖");
            check(!e.isDropItems(), "不掉普通的木桶");
            check(((Barrel) b.getState(false)).getInventory().isEmpty(), "木桶裡的備貨清掉了（不會散一地）");
            eq(0, displays(b).size(), "挖掉後顯示實體都移除");
            b.setType(Material.AIR);
        });
        step(2, "挖掉：檢查掉落物", () -> {
            List<Item> items = drops(b);
            List<Item> barrels = items.stream().filter(i -> i.getItemStack().getType() == Material.BARREL).toList();
            eq(1, barrels.size(), "掉出一個抽屜");
            eq(0, items.stream().filter(i -> i.getItemStack().getType() == Material.COBBLESTONE).count(),
                    "沒有散落的鵝卵石");
            if (barrels.isEmpty()) {
                return;
            }
            ItemStack item = barrels.get(0).getItemStack();
            Contents c = read(item.getItemMeta().getPersistentDataContainer());
            eq(500, c.total(), "抽屜物品裡記著 500 個");
            eq(Material.COBBLESTONE, c.type(0), "抽屜物品裡記著鵝卵石");
            check(c.locked() && c.upgrades().equals(List.of(1)), "抽屜物品記著鎖定和升級");
            eq(1, item.getMaxStackSize(), "裝了東西的抽屜不能疊");
            String lore = item.lore() == null ? "" : item.lore().stream()
                    .map(l -> PlainTextComponentSerializer.plainText().serialize(l)).reduce("", (a, l) -> a + l + "|");
            check(lore.contains("×500"), "說明文字寫著 ×500（" + lore + "）");
            dropped[0] = item;
            for (Item i : items) {
                i.remove();
            }
        });
        step(1, "放回去：內容、升級、鎖定都還在", () -> {
            if (dropped[0] == null) {
                fail("沒有掉落的抽屜可以放");
                return;
            }
            BlockState replaced = b.getState();
            b.setType(Material.BARREL);
            FakePlayer placer = playerFacing(b, BlockFace.SOUTH);
            fire(new BlockPlaceEvent(b, replaced, b.getRelative(BlockFace.DOWN), dropped[0], placer.player, true,
                    EquipmentSlot.HAND));
            eq(BlockFace.SOUTH, ((Directional) b.getBlockData()).getFacing(), "放下的抽屜面向放的人");
            Contents c = contents(b);
            eq(500, c == null ? -1 : c.counts[0], "放回去還是 500 個");
            check(c != null && c.locked() && c.upgrades().equals(List.of(1)), "放回去還是鎖定、一級升級");
            Map<String, Display> ds = displays(b);
            check(ds.containsKey("icon0") && ds.containsKey("count0") && ds.containsKey("lock"), "放回去顯示都長回來");
        });
        step(1, "正面打一下同一刻就挖掉（瞬間挖掉）會被擋", () -> {
            leftClick(p[0], b, f, 0, 0);
            BlockBreakEvent e = breakBlock(p[0], b);
            check(e.isCancelled(), "正面瞬間挖掉被擋下");
            eq(436, contents(b).counts[0], "那一下只拿了一組（剩 436）");
        });
        step(1, "正面挖了一段時間才挖掉可以", () -> {
            BlockBreakEvent e = breakBlock(p[0], b);
            check(!e.isCancelled(), "不是同一刻就可以挖掉");
            b.setType(Material.AIR);
        });
        step(2, "正面挖掉的掉落物", () -> {
            List<Item> items = drops(b);
            long total = items.stream().filter(i -> i.getItemStack().getType() == Material.BARREL)
                    .mapToLong(i -> read(i.getItemStack().getItemMeta().getPersistentDataContainer()).total()).sum();
            eq(436, total, "掉出的抽屜裡有 436 個");
            for (Item i : items) {
                i.remove();
            }
        });
    }

    private void creativeAndCrafting() {
        Block b = block(39);
        BlockFace f = BlockFace.SOUTH;
        FakePlayer[] p = new FakePlayer[1];
        step(1, "創造模式挖空抽屜", () -> {
            place(b, 1, f);
            p[0] = playerFacing(b, f);
            p[0].mode = GameMode.CREATIVE;
            check(!breakBlock(p[0], b).isCancelled(), "創造模式從側面可以挖");
            b.setType(Material.AIR);
        });
        step(2, "創造模式挖空抽屜不掉東西", () -> {
            eq(0, drops(b).size(), "創造模式挖空抽屜不掉落");
            place(b, 1, f);
            p[0].storage.setItem(0, new ItemStack(Material.DIRT, 1));
            rightClick(p[0], b, f, 0, 0);
            check(!breakBlock(p[0], b).isCancelled(), "創造模式挖有東西的抽屜");
            b.setType(Material.AIR);
        });
        step(2, "創造模式挖有東西的抽屜會掉", () -> {
            List<Item> items = drops(b);
            eq(1, items.size(), "創造模式挖有東西的抽屜掉一個");
            items.forEach(Entity::remove);
            p[0].mode = GameMode.SURVIVAL;
            place(b, 1, f);
            breakBlock(p[0], b);
            b.setType(Material.AIR);
        });
        step(2, "合成表、空抽屜能跟合成的疊在一起", () -> {
            List<Item> items = drops(b);
            Material P = Material.OAK_PLANKS;
            Material S = Material.SPRUCE_PLANKS;
            Material C = Material.CHEST;
            ItemStack single = craft(P, P, P, P, C, P, P, P, P);
            ItemStack mixed = craft(P, S, P, S, C, S, P, S, P);
            ItemStack dbl = craft(P, C, P, P, P, P, P, C, P);
            ItemStack quad = craft(C, P, C, P, P, P, C, P, C);
            eq(Material.BARREL, single.getType(), "單格抽屜合成");
            eq(1, read(single.getItemMeta().getPersistentDataContainer()).templates().length, "合成的單格是 1 格");
            eq(Material.BARREL, mixed.getType(), "不同木材混著也能合成");
            eq(2, dbl.getAmount(), "雙格抽屜一次 2 個");
            eq(2, read(dbl.getItemMeta().getPersistentDataContainer()).templates().length, "雙格是 2 格");
            eq(4, quad.getAmount(), "四格抽屜一次 4 個");
            eq(4, read(quad.getItemMeta().getPersistentDataContainer()).templates().length, "四格是 4 格");
            for (int t = 1; t <= 5; t++) {
                eq(t, tierOf(upgradeItem(t)), "第 " + t + " 級升級合成");
            }
            eq(1, items.size(), "生存挖空抽屜掉一個");
            if (!items.isEmpty()) {
                ItemStack blank = items.get(0).getItemStack();
                check(blank.isSimilar(single), "挖下來的空抽屜跟合成的一樣，可以疊");
                eq(64, blank.getMaxStackSize(), "空抽屜一疊 64");
            }
            items.forEach(Entity::remove);
        });
    }

    /**
     * Creative breaks are instant and always start with a hit on the face, so
     * a front hit that took nothing has to let the break through.
     */
    private void creativeFront() {
        Block b = block(42);
        BlockFace f = BlockFace.SOUTH;
        FakePlayer[] p = new FakePlayer[1];
        step(1, "創造模式從正面挖空抽屜", () -> {
            place(b, 1, f);
            p[0] = playerFacing(b, f);
            p[0].mode = GameMode.CREATIVE;
            leftClick(p[0], b, f, 0, 0);
            BlockBreakEvent e = breakBlock(p[0], b);
            check(!e.isCancelled(), "創造模式從正面一下就能挖掉空抽屜");
            b.setType(Material.AIR);
        });
        step(2, "創造模式從正面挖有東西的抽屜", () -> {
            eq(0, drops(b).size(), "創造模式從正面挖空抽屜不掉落");
            place(b, 1, f);
            p[0].storage.clear();
            p[0].storage.setItem(0, new ItemStack(Material.DIRT, 64));
            rightClick(p[0], b, f, 0, 0);
            p[0].storage.clear();
        });
        step(CLICK_GAP, "創造模式正面第一下拿東西", () -> {
            leftClick(p[0], b, f, 0, 0);
            check(breakBlock(p[0], b).isCancelled(), "有拿到東西的那一下不會順便挖掉抽屜");
            eq(64, count(p[0].storage, Material.DIRT), "那一下拿到一組泥土");
            eq(0, contents(b).counts[0], "抽屜拿空了");
        });
        step(1, "創造模式正面第二下挖掉", () -> {
            leftClick(p[0], b, f, 0, 0);
            check(!breakBlock(p[0], b).isCancelled(), "拿空之後再打一下就挖掉");
            b.setType(Material.AIR);
        });
        step(2, "創造模式正面挖掉之後", () -> {
            eq(0, drops(b).size(), "拿空的抽屜在創造模式不掉落");
        });
    }

    private void explosions() {
        Block a = block(60);
        Block t = block(68);
        BlockFace f = BlockFace.SOUTH;
        Location[] iconBefore = new Location[2];
        step(1, "爆炸：準備", () -> {
            for (Block b : List.of(a, t)) {
                place(b, 1, f);
                FakePlayer p = playerFacing(b, f);
                p.storage.setItem(0, new ItemStack(Material.COBBLESTONE, 64));
                rightClick(p, b, f, 0, 0);
            }
            iconBefore[0] = displays(a).get("icon0").getLocation();
            iconBefore[1] = displays(t).get("icon0").getLocation();
            world.createExplosion(a.getLocation().add(0.5, 0.5, 1.5), 4f, false, true);
            TNTPrimed tnt = world.spawn(t.getLocation().add(0.5, 0, 1.5), TNTPrimed.class);
            tnt.setFuseTicks(1);
        });
        step(10, "爆炸：抽屜還在", () -> {
            eq(64, contents(a) == null ? -1 : contents(a).counts[0], "直接爆炸後抽屜和 64 個都還在");
            eq(64, contents(t) == null ? -1 : contents(t).counts[0], "TNT 爆炸後抽屜和 64 個都還在");
            check(world.getBlockAt(a.getX(), Y - 1, Z + 1).getType().isAir(), "（對照）旁邊的草地確實被炸掉");
            Display ia = displays(a).get("icon0");
            Display it = displays(t).get("icon0");
            check(ia != null && ia.getLocation().distance(iconBefore[0]) < 0.01, "直接爆炸沒有把圖示炸歪");
            check(it != null && it.getLocation().distance(iconBefore[1]) < 0.01, "TNT 沒有把圖示炸歪");
        });
    }

    private void misc() {
        Block b = block(45);
        Block quad = block(48);
        Block sword = block(51);
        Block plain = block(54);
        BlockFace f = BlockFace.SOUTH;
        FakePlayer[] p = new FakePlayer[1];
        step(1, "其他：著火、側面、開木桶介面", () -> {
            place(b, 1, f);
            p[0] = playerFacing(b, f);
            p[0].storage.setItem(0, new ItemStack(Material.COBBLESTONE, 10));
            rightClick(p[0], b, f, 0, 0);
            BlockBurnEvent burn = new BlockBurnEvent(b, null);
            fire(burn);
            check(burn.isCancelled(), "抽屜不會被火燒掉");
            p[0].storage.setItem(0, new ItemStack(Material.COBBLESTONE, 5));
            PlayerInteractEvent top = rightClick(p[0], b, BlockFace.UP, 0, 0);
            check(top.useInteractedBlock() != Event.Result.DENY, "點上面不算抽屜操作");
            eq(10, contents(b).counts[0], "點上面不會放東西進去");
            InventoryOpenEvent open = new InventoryOpenEvent(p[0].view(((Barrel) b.getState(false)).getInventory()));
            fire(open);
            check(open.isCancelled(), "抽屜的木桶介面打不開");
            plain.setType(Material.BARREL);
            PlayerInteractEvent e = rightClick(p[0], plain, f, 0, 0);
            check(e.useInteractedBlock() != Event.Result.DENY, "普通木桶右鍵不受影響");
            InventoryOpenEvent plainOpen = new InventoryOpenEvent(
                    p[0].view(((Barrel) plain.getState(false)).getInventory()));
            fire(plainOpen);
            check(!plainOpen.isCancelled(), "普通木桶照常打開");
        });
        step(CLICK_GAP, "其他：很快地連續放兩種不同的東西", () -> {
            place(quad, 4, f);
            FakePlayer q = playerFacing(quad, f);
            q.storage.setItem(0, new ItemStack(Material.STONE, 64));
            rightClick(q, quad, f, -0.25, 0.25);
            q.storage.setItem(0, new ItemStack(Material.DIRT, 64));
            rightClick(q, quad, f, 0.25, 0.25);
            eq(Material.DIRT, contents(quad).type(1), "400 毫秒內換東西再按，第二種也放得進去");
            eq(64, contents(quad).counts[0], "換東西那下石頭數量沒變");
            q.storage.setItem(0, new ItemStack(Material.STONE, 10));
            q.storage.setItem(5, new ItemStack(Material.STONE, 20));
            rightClick(q, quad, f, 0.25, -0.25);
            eq(64 + 30, contents(quad).counts[0], "拿著抽屜裡已有的東西連點，背包裡的石頭全收進去");
            eq(0, count(q.storage, Material.STONE), "背包裡的石頭都放進去了");
        });
        step(1, "其他：工具類（不能疊的東西）", () -> {
            place(sword, 1, f);
            FakePlayer s = playerFacing(sword, f);
            s.storage.setItem(0, new ItemStack(Material.DIAMOND_SWORD));
            rightClick(s, sword, f, 0, 0);
            eq(1, contents(sword).counts[0], "放進一把鑽石劍");
            p[0] = s;
        });
        step(CLICK_GAP, "其他：附魔過的劍算不同的東西", () -> {
            ItemStack enchanted = new ItemStack(Material.DIAMOND_SWORD);
            enchanted.addEnchantment(Enchantment.SHARPNESS, 1);
            p[0].storage.setItem(0, enchanted);
            rightClick(p[0], sword, f, 0, 0);
            eq(1, contents(sword).counts[0], "附魔劍不會混進普通劍那格");
            check(!p[0].hand().isEmpty(), "附魔劍還在手上");
        });
    }

    /** /drawers buy as the player menu runs it: 3 plain iron ingots for one single drawer (the default config). */
    private void buying() {
        step(1, "兌換：權限", () -> {
            FakePlayer p = playerFacing(block(57), BlockFace.SOUTH);
            p.storage.setItem(0, new ItemStack(Material.IRON_INGOT, 3));
            command(p, "buy");
            eq(3, count(p.storage, Material.IRON_INGOT), "沒有 drawers.buy 權限不能換");
            p.permissions.add("drawers.buy");
            command(p, "give", "DrawerTester", "quad");
            eq(0, count(p.storage, Material.BARREL), "一般玩家不能用管理員的 give");
            check(p.lastMessage().contains("沒有權限"), "一般玩家用 give 會說沒有權限（" + p.lastMessage() + "）");
        });
        step(1, "兌換：材料不夠", () -> {
            FakePlayer p = playerFacing(block(57), BlockFace.SOUTH);
            p.permissions.add("drawers.buy");
            p.storage.setItem(0, new ItemStack(Material.IRON_INGOT, 2));
            command(p, "buy");
            eq(2, count(p.storage, Material.IRON_INGOT), "只有 2 個鐵錠時不會被拿走");
            eq(0, count(p.storage, Material.BARREL), "只有 2 個鐵錠換不到抽屜");
            check(p.lastMessage().contains("你身上有 2 個"), "會說還差多少（" + p.lastMessage() + "）");
        });
        step(1, "兌換：換到抽屜", () -> {
            FakePlayer p = playerFacing(block(57), BlockFace.SOUTH);
            p.permissions.add("drawers.buy");
            ItemStack named = new ItemStack(Material.IRON_INGOT, 5);
            ItemMeta meta = named.getItemMeta();
            meta.displayName(net.kyori.adventure.text.Component.text("特別的鐵"));
            named.setItemMeta(meta);
            p.storage.setItem(0, named);
            p.storage.setItem(3, new ItemStack(Material.IRON_INGOT, 2));
            p.storage.setItem(7, new ItemStack(Material.IRON_INGOT, 2));
            command(p, "buy");
            eq(1, count(p.storage, Material.BARREL), "4 個普通鐵錠換到 1 個抽屜");
            ItemStack got = null;
            for (ItemStack s : p.storage.getContents()) {
                if (s != null && s.getType() == Material.BARREL) {
                    got = s;
                }
            }
            check(got != null && got.hasItemMeta()
                    && got.getItemMeta().getPersistentDataContainer().has(SLOTS), "換到的是抽屜，不是普通木桶");
            eq(1, got == null ? -1 : read(got.getItemMeta().getPersistentDataContainer()).templates().length,
                    "換到的是單格抽屜");
            eq(5, p.storage.getItem(0) == null ? 0 : p.storage.getItem(0).getAmount(), "改過名的鐵錠一個都沒拿");
            int plain = 0;
            for (ItemStack s : p.storage.getContents()) {
                if (s != null && s.isSimilar(new ItemStack(Material.IRON_INGOT))) {
                    plain += s.getAmount();
                }
            }
            eq(1, plain, "普通鐵錠剛好拿走 3 個（兩疊湊起來）");
            command(p, "buy");
            eq(1, count(p.storage, Material.BARREL), "剩 1 個普通鐵錠時不能再換");
            ItemStack drawer = craft(Material.OAK_PLANKS, Material.OAK_PLANKS, Material.OAK_PLANKS,
                    Material.OAK_PLANKS, Material.CHEST, Material.OAK_PLANKS,
                    Material.OAK_PLANKS, Material.OAK_PLANKS, Material.OAK_PLANKS);
            check(got != null && got.isSimilar(drawer), "換到的抽屜跟合成出來的可以疊在一起");
        });
    }

    private void command(FakePlayer p, String... args) {
        getServer().getPluginCommand("drawers").execute(p.player, "drawers", args);
    }

    /** A drawer removed behind the plugin's back (/setblock) loses its displays on the next chunk load. */
    private void orphans() {
        Block b = world.getBlockAt(200, Y, 200);
        String key = "200," + Y + ",200";
        BoundingBox box = BoundingBox.of(b).expand(1);
        step(1, "孤兒顯示：用 setblock 的方式拿掉抽屜", () -> {
            place(b, 1, BlockFace.SOUTH);
            FakePlayer p = playerFacing(b, BlockFace.SOUTH);
            p.storage.setItem(0, new ItemStack(Material.DIRT, 64));
            rightClick(p, b, BlockFace.SOUTH, 0, 0);
            eq(2, displayCount(key, box), "放東西後有圖示和數字");
            ((Barrel) b.getState(false)).getInventory().clear();
            b.setType(Material.AIR);
            eq(2, displayCount(key, box), "（對照）直接拿掉方塊時顯示還留著");
            world.unloadChunk(b.getX() >> 4, b.getZ() >> 4, true);
        });
        boolean[] reloaded = new boolean[1];
        step(40, "孤兒顯示：重新載入區塊", () -> {
            reloaded[0] = !world.isChunkLoaded(b.getX() >> 4, b.getZ() >> 4);
            getLogger().info("區塊有真的卸載：" + reloaded[0]);
            world.getChunkAt(b).addPluginChunkTicket(this);
        });
        step(60, "孤兒顯示：檢查", () -> {
            Chunk chunk = world.getChunkAt(b);
            check(chunk.isEntitiesLoaded(), "區塊的實體載入了");
            if (reloaded[0]) {
                eq(0, displayCount(key, box), "區塊重新載入後孤兒顯示被清掉");
            } else {
                // The chunk never unloaded, so no load event came: hand the
                // listener the event a reload would have produced.
                List<Entity> orphans = new ArrayList<>(world.getNearbyEntities(box, e -> e instanceof Display));
                fire(new org.bukkit.event.world.EntitiesLoadEvent(chunk, orphans));
                eq(0, displayCount(key, box), "（模擬載入事件）孤兒顯示被清掉");
            }
            chunk.removePluginChunkTicket(this);
        });
    }

    private static String fmt(double d) {
        return String.format(Locale.ROOT, "%.2f", d);
    }
}
