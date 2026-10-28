package tw.ryanchiu.drawers;

import org.bukkit.NamespacedKey;

/** Persistent-data keys, shared by drawer blocks, drawer items and their displays. */
final class Keys {

    private static final String NS = "ryandrawers";

    /** 1, 2 or 4 - present on every drawer block and drawer item. */
    static final NamespacedKey SLOTS = new NamespacedKey(NS, "slots");
    /** One serialized template per slot; an empty array means an unassigned slot. */
    static final NamespacedKey ITEMS = new NamespacedKey(NS, "items");
    static final NamespacedKey COUNTS = new NamespacedKey(NS, "counts");
    static final NamespacedKey LOCKED = new NamespacedKey(NS, "locked");
    /** Installed upgrade tiers, 1-5. */
    static final NamespacedKey UPGRADES = new NamespacedKey(NS, "upgrades");
    /** On an upgrade item: its tier. */
    static final NamespacedKey UPGRADE = new NamespacedKey(NS, "upgrade");
    /** On a display entity: "x,y,z" of the drawer it belongs to. */
    static final NamespacedKey OWNER = new NamespacedKey(NS, "owner");
    /** On a display entity: what it shows, e.g. "icon0", "count0", "lock". */
    static final NamespacedKey ROLE = new NamespacedKey(NS, "role");

    private Keys() {
    }
}
