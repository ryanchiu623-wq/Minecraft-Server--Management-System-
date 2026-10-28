package tw.ryanchiu.drawers;

import java.util.ArrayList;
import java.util.List;

import org.bukkit.Material;
import org.bukkit.block.Barrel;
import org.bukkit.block.Block;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;

/**
 * What one drawer holds: per slot, the item it is assigned to and how many.
 *
 * The barrel's own inventory doubles as the hopper interface. On disk the
 * drawer is "persistent-data count + whatever sits in the barrel": store()
 * puts up to one stack of each slot's item in barrel slot i so hoppers can
 * pull it, and load() folds the barrel's contents back into the counts - which
 * also absorbs anything a hopper pushed in since. Code in between only ever
 * sees full totals.
 */
final class DrawerData {

    final int slots;
    final ItemStack[] templates;
    final long[] counts;
    boolean locked;
    final List<Integer> upgrades = new ArrayList<>();
    /** Barrel contents no slot would take. The caller drops them. */
    final List<ItemStack> overflow = new ArrayList<>();

    DrawerData(int slots) {
        this.slots = slots;
        this.templates = new ItemStack[slots];
        this.counts = new long[slots];
    }

    static boolean isDrawer(PersistentDataContainer pdc) {
        return pdc.has(Keys.SLOTS, PersistentDataType.INTEGER);
    }

    static boolean isDrawer(Block block) {
        return block.getType() == Material.BARREL
                && block.getState(false) instanceof Barrel barrel
                && isDrawer(barrel.getPersistentDataContainer());
    }

    /** Reads the persistent data alone: on a block these counts exclude the barrel's stock. */
    static DrawerData read(PersistentDataContainer pdc) {
        int slots = pdc.getOrDefault(Keys.SLOTS, PersistentDataType.INTEGER, 1);
        DrawerData d = new DrawerData(slots == 2 || slots == 4 ? slots : 1);
        List<byte[]> items = pdc.get(Keys.ITEMS, PersistentDataType.LIST.byteArrays());
        long[] counts = pdc.get(Keys.COUNTS, PersistentDataType.LONG_ARRAY);
        for (int i = 0; i < d.slots; i++) {
            if (items != null && i < items.size() && items.get(i).length > 0) {
                d.templates[i] = ItemStack.deserializeBytes(items.get(i));
            }
            if (counts != null && i < counts.length) {
                d.counts[i] = Math.max(0, counts[i]);
            }
        }
        d.locked = pdc.getOrDefault(Keys.LOCKED, PersistentDataType.BOOLEAN, false);
        int[] ups = pdc.get(Keys.UPGRADES, PersistentDataType.INTEGER_ARRAY);
        if (ups != null) {
            for (int u : ups) {
                d.upgrades.add(u);
            }
        }
        return d;
    }

    /** Persistent data plus the barrel's contents: full totals. */
    static DrawerData load(PersistentDataContainer pdc, Inventory barrel) {
        DrawerData d = read(pdc);
        for (ItemStack item : barrel.getContents()) {
            if (item == null || item.isEmpty()) {
                continue;
            }
            // No capacity check: stock was already counted when it went out,
            // and hopper input was checked before it was let in.
            int s = d.slotFor(item);
            if (s < 0) {
                d.overflow.add(item.clone());
                continue;
            }
            if (d.templates[s] == null) {
                d.templates[s] = item.asOne();
            }
            d.counts[s] += item.getAmount();
        }
        d.forgetEmpty();
        return d;
    }

    static DrawerData load(Barrel state) {
        return load(state.getPersistentDataContainer(), state.getSnapshotInventory());
    }

    /** Writes this drawer back into a barrel snapshot and applies it. */
    void store(Barrel state) {
        Inventory inv = state.getSnapshotInventory();
        inv.clear();
        long[] stored = counts.clone();
        for (int i = 0; i < slots; i++) {
            if (templates[i] != null && counts[i] > 0) {
                int stock = (int) Math.min(counts[i], templates[i].getMaxStackSize());
                inv.setItem(i, templates[i].asQuantity(stock));
                stored[i] -= stock;
            }
        }
        write(state.getPersistentDataContainer(), stored);
        // The snapshot carries both the inventory and the persistent data, so
        // one update applies them together.
        state.update(true, false);
    }

    void write(PersistentDataContainer pdc, long[] storedCounts) {
        pdc.set(Keys.SLOTS, PersistentDataType.INTEGER, slots);
        List<byte[]> items = new ArrayList<>(slots);
        for (ItemStack t : templates) {
            items.add(t == null ? new byte[0] : t.serializeAsBytes());
        }
        pdc.set(Keys.ITEMS, PersistentDataType.LIST.byteArrays(), items);
        pdc.set(Keys.COUNTS, PersistentDataType.LONG_ARRAY, storedCounts);
        pdc.set(Keys.LOCKED, PersistentDataType.BOOLEAN, locked);
        pdc.set(Keys.UPGRADES, PersistentDataType.INTEGER_ARRAY,
                upgrades.stream().mapToInt(Integer::intValue).toArray());
    }

    /** True for a drawer that is no different from a freshly crafted one. */
    boolean isBlank() {
        if (locked || !upgrades.isEmpty()) {
            return false;
        }
        for (int i = 0; i < slots; i++) {
            if (templates[i] != null || counts[i] > 0) {
                return false;
            }
        }
        return true;
    }

    int multiplier() {
        int sum = 0;
        for (int tier : upgrades) {
            sum += RyanDrawers.settings().multiplier(tier);
        }
        return Math.max(1, sum);
    }

    long capacity(int slot) {
        return capacityFor(templates[slot], multiplier());
    }

    long capacityFor(ItemStack item, int multiplier) {
        int stack = item == null ? 64 : item.getMaxStackSize();
        return RyanDrawers.settings().baseStacks(slots) * stack * multiplier;
    }

    /** The slot already holding this item, or -1. */
    int matchSlot(ItemStack item) {
        for (int i = 0; i < slots; i++) {
            if (templates[i] != null && templates[i].isSimilar(item)) {
                return i;
            }
        }
        return -1;
    }

    /** Where this item belongs: the slot holding it, else the first unassigned slot, else -1. */
    int slotFor(ItemStack item) {
        int s = matchSlot(item);
        if (s >= 0) {
            return s;
        }
        for (int i = 0; i < slots; i++) {
            if (templates[i] == null) {
                return i;
            }
        }
        return -1;
    }

    /** How many of this item would still fit. */
    long room(ItemStack item) {
        int s = slotFor(item);
        if (s < 0) {
            return 0;
        }
        return Math.max(0, capacityFor(item, multiplier()) - counts[s]);
    }

    /**
     * Adds up to amount of item and returns how many went in. An item the
     * drawer already holds goes to its slot; a new one to the clicked slot if
     * that is free, else to the first free slot.
     */
    long insert(ItemStack item, long amount, int preferred) {
        int s = matchSlot(item);
        if (s < 0) {
            s = preferred >= 0 && preferred < slots && templates[preferred] == null
                    ? preferred : slotFor(item);
        }
        if (s < 0) {
            return 0;
        }
        long n = Math.min(amount, capacityFor(item, multiplier()) - counts[s]);
        if (n <= 0) {
            return 0;
        }
        if (templates[s] == null) {
            templates[s] = item.asOne();
        }
        counts[s] += n;
        return n;
    }

    /** Takes up to amount from a slot, or null if it is empty. */
    ItemStack take(int slot, int amount) {
        if (templates[slot] == null || counts[slot] <= 0 || amount <= 0) {
            return null;
        }
        int n = (int) Math.min(counts[slot], Math.min(amount, templates[slot].getMaxStackSize()));
        ItemStack out = templates[slot].asQuantity(n);
        counts[slot] -= n;
        forgetEmpty();
        return out;
    }

    /** An emptied slot forgets its item unless the drawer is locked, as in the mod. */
    void forgetEmpty() {
        for (int i = 0; i < slots; i++) {
            if (counts[i] <= 0) {
                counts[i] = 0;
                if (!locked) {
                    templates[i] = null;
                }
            }
        }
    }

    boolean fitsWithMultiplier(int multiplier) {
        for (int i = 0; i < slots; i++) {
            if (templates[i] != null && counts[i] > capacityFor(templates[i], multiplier)) {
                return false;
            }
        }
        return true;
    }

    int multiplierWithout(int index) {
        int sum = 0;
        for (int i = 0; i < upgrades.size(); i++) {
            if (i != index) {
                sum += RyanDrawers.settings().multiplier(upgrades.get(i));
            }
        }
        return Math.max(1, sum);
    }
}
