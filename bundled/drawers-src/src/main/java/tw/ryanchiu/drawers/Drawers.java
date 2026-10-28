package tw.ryanchiu.drawers;

import java.util.LinkedHashSet;
import java.util.Set;

import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.block.Barrel;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.block.data.Directional;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/** Shared drawer operations: saving, creating, and the deferred hopper sync. */
final class Drawers {

    private final RyanDrawers plugin;
    private final Displays displays;
    private final Set<Block> pending = new LinkedHashSet<>();

    Drawers(RyanDrawers plugin, Displays displays) {
        this.plugin = plugin;
        this.displays = displays;
    }

    Displays displays() {
        return displays;
    }

    /** Writes d into the barrel, drops anything it could not hold, and redraws. */
    void save(Block block, Barrel state, DrawerData d) {
        d.store(state);
        for (ItemStack extra : d.overflow) {
            block.getWorld().dropItemNaturally(block.getLocation().add(0.5, 1.1, 0.5), extra);
        }
        d.overflow.clear();
        displays.refresh(block, d);
    }

    /** Turns the block into a drawer with these contents, facing the given way. */
    void create(Block block, BlockFace facing, DrawerData d) {
        if (block.getType() != Material.BARREL) {
            block.setType(Material.BARREL, false);
        }
        if (block.getBlockData() instanceof Directional dir) {
            dir.setFacing(facing);
            block.setBlockData(dir, false);
        }
        save(block, (Barrel) block.getState(), d);
    }

    /**
     * A hopper moved something in or out: fold the barrel's contents back in
     * and restock on the next tick, once the move has actually happened.
     */
    void syncLater(Block block) {
        if (pending.isEmpty()) {
            Bukkit.getScheduler().runTask(plugin, this::flush);
        }
        pending.add(block);
    }

    private void flush() {
        Block[] blocks = pending.toArray(Block[]::new);
        pending.clear();
        for (Block block : blocks) {
            if (DrawerData.isDrawer(block)) {
                Barrel state = (Barrel) block.getState();
                save(block, state, DrawerData.load(state));
            }
        }
    }

    static void give(Player player, ItemStack item) {
        for (ItemStack left : player.getInventory().addItem(item).values()) {
            player.getWorld().dropItemNaturally(player.getLocation(), left);
        }
    }
}
