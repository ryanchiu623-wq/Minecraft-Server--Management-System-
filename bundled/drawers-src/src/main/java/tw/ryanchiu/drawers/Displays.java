package tw.ryanchiu.drawers;

import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.bukkit.Color;
import org.bukkit.Location;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.data.Directional;
import org.bukkit.entity.Display;
import org.bukkit.entity.Entity;
import org.bukkit.entity.ItemDisplay;
import org.bukkit.entity.TextDisplay;
import org.bukkit.inventory.ItemStack;
import org.bukkit.persistence.PersistentDataType;
import org.bukkit.util.BoundingBox;
import org.bukkit.util.Transformation;
import org.bukkit.util.Vector;
import org.joml.Quaternionf;
import org.joml.Vector3f;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;

/**
 * The item icons and counts floating on a drawer's front.
 *
 * They are ordinary display entities tagged with the drawer's coordinates,
 * found again by that tag rather than by stored UUIDs, so a drawer whose
 * displays were killed simply grows new ones on its next update.
 */
final class Displays {

    /** Where one slot's icon and count go on the face, in face units (-0.5..0.5). */
    private record Spot(double iconU, double iconV, float iconScale,
                        double countU, double countV, float countScale) {
    }

    private static final Spot[] SINGLE = {new Spot(0, 0.08, 0.5f, 0, -0.38, 0.55f)};
    private static final Spot[] DOUBLE = {
            new Spot(0, 0.29, 0.3f, 0, 0.04, 0.4f),
            new Spot(0, -0.2, 0.3f, 0, -0.47, 0.4f)};
    private static final Spot[] QUAD = new Spot[4];

    static {
        for (int k = 0; k < 4; k++) {
            double u = k % 2 == 0 ? -0.25 : 0.25;
            double v = k < 2 ? 0.25 : -0.25;
            QUAD[k] = new Spot(u, v + 0.06, 0.26f, u, v - 0.2, 0.32f);
        }
    }

    static String ownerKey(Block b) {
        return b.getX() + "," + b.getY() + "," + b.getZ();
    }

    static BlockFace facing(Block b) {
        return b.getBlockData() instanceof Directional dir ? dir.getFacing() : BlockFace.NORTH;
    }

    /** Brings the displays in line with the drawer's contents. */
    void refresh(Block block, DrawerData d) {
        BlockFace face = facing(block);
        Map<String, Display> existing = new HashMap<>();
        for (Display e : find(block)) {
            String role = e.getPersistentDataContainer().get(Keys.ROLE, PersistentDataType.STRING);
            if (role == null || existing.containsKey(role)) {
                e.remove();
            } else {
                existing.put(role, e);
            }
        }
        Spot[] spots = d.slots == 4 ? QUAD : d.slots == 2 ? DOUBLE : SINGLE;
        Set<String> wanted = new HashSet<>();

        for (int i = 0; i < d.slots; i++) {
            ItemStack t = d.templates[i];
            if (t == null) {
                continue;
            }
            Spot s = spots[i];
            String iconRole = "icon" + i;
            wanted.add(iconRole);
            ItemDisplay icon = existing.get(iconRole) instanceof ItemDisplay id ? id
                    : spawnIcon(block, face, iconRole, s);
            if (!t.isSimilar(icon.getItemStack())) {
                icon.setItemStack(t);
            }

            String countRole = "count" + i;
            wanted.add(countRole);
            TextDisplay count = existing.get(countRole) instanceof TextDisplay td ? td
                    : spawnText(block, face, countRole, s.countU(), s.countV(), s.countScale());
            boolean full = d.counts[i] >= d.capacity(i);
            count.text(Component.text(format(d.counts[i]),
                    full ? NamedTextColor.GOLD : d.counts[i] == 0 ? NamedTextColor.GRAY : NamedTextColor.WHITE));
        }

        if (d.locked) {
            wanted.add("lock");
            TextDisplay lock = existing.get("lock") instanceof TextDisplay td ? td
                    : spawnText(block, face, "lock", 0.43, 0.41, 0.3f);
            lock.text(Component.text("鎖", NamedTextColor.GOLD));
        }

        for (Map.Entry<String, Display> e : existing.entrySet()) {
            if (!wanted.contains(e.getKey())) {
                e.getValue().remove();
            }
        }
    }

    void remove(Block block) {
        for (Display e : find(block)) {
            e.remove();
        }
    }

    int count(Block block) {
        return find(block).size();
    }

    private List<Display> find(Block block) {
        String key = ownerKey(block);
        BoundingBox box = BoundingBox.of(block).expand(0.3);
        return block.getWorld().getNearbyEntities(box, e -> e instanceof Display
                        && key.equals(e.getPersistentDataContainer().get(Keys.OWNER, PersistentDataType.STRING)))
                .stream().map(e -> (Display) e).toList();
    }

    private ItemDisplay spawnIcon(Block block, BlockFace face, String role, Spot s) {
        return block.getWorld().spawn(at(block, face, s.iconU(), s.iconV(), 0.02), ItemDisplay.class, e -> {
            tag(e, block, role);
            // GUI is how the item looks in an inventory - flat icons and
            // little isometric blocks, as the mod draws them. The near-zero
            // depth presses blocks flat against the face.
            e.setItemDisplayTransform(ItemDisplay.ItemDisplayTransform.GUI);
            e.setTransformation(new Transformation(new Vector3f(), new Quaternionf(),
                    new Vector3f(s.iconScale(), s.iconScale(), 0.01f), new Quaternionf()));
        });
    }

    private TextDisplay spawnText(Block block, BlockFace face, String role, double u, double v, float scale) {
        return block.getWorld().spawn(at(block, face, u, v, 0.03), TextDisplay.class, e -> {
            tag(e, block, role);
            e.setBillboard(Display.Billboard.FIXED);
            e.setAlignment(TextDisplay.TextAlignment.CENTER);
            e.setDefaultBackground(false);
            e.setBackgroundColor(Color.fromARGB(0, 0, 0, 0));
            e.setShadowed(true);
            e.setTransformation(new Transformation(new Vector3f(), new Quaternionf(),
                    new Vector3f(scale, scale, scale), new Quaternionf()));
        });
    }

    private void tag(Display e, Block block, String role) {
        e.getPersistentDataContainer().set(Keys.OWNER, PersistentDataType.STRING, ownerKey(block));
        e.getPersistentDataContainer().set(Keys.ROLE, PersistentDataType.STRING, role);
        e.setViewRange(RyanDrawers.settings().viewRange());
        e.setPersistent(true);
    }

    /**
     * A point on the drawer's face, just outside it, turned to look the way
     * the face does - a fixed display's front points along its yaw.
     * u runs left to right as seen by someone facing the drawer, v upward.
     */
    private static Location at(Block b, BlockFace face, double u, double v, double out) {
        Vector right = new Vector(face.getModZ(), 0, -face.getModX());
        Location loc = b.getLocation().add(0.5, 0.5, 0.5)
                .add(face.getModX() * (0.5 + out), v, face.getModZ() * (0.5 + out))
                .add(right.multiply(u));
        loc.setDirection(face.getDirection());
        return loc;
    }

    /** Which slot a point on the face falls in. */
    static int slotAt(Block b, BlockFace face, Vector hit, int slots) {
        if (slots == 1 || hit == null) {
            return 0;
        }
        double dx = hit.getX() - (b.getX() + 0.5);
        double dz = hit.getZ() - (b.getZ() + 0.5);
        double u = dx * face.getModZ() - dz * face.getModX();
        double v = hit.getY() - (b.getY() + 0.5);
        if (slots == 2) {
            return v >= 0 ? 0 : 1;
        }
        return (v >= 0 ? 0 : 2) + (u >= 0 ? 1 : 0);
    }

    static String format(long n) {
        if (n < 100_000) {
            return Long.toString(n);
        }
        if (n < 10_000_000) {
            return (n / 1000) + "k";
        }
        return (n / 1_000_000) + "M";
    }

    /** True for a display that belongs to the drawer key it carries. */
    static boolean isOurs(Entity e) {
        return e instanceof Display && e.getPersistentDataContainer().has(Keys.OWNER, PersistentDataType.STRING);
    }
}
