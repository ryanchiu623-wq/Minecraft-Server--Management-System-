package tw.ryanchiu.drawers;

import java.util.List;

import org.bukkit.Material;
import org.bukkit.configuration.file.FileConfiguration;

/** config.yml, read once on enable. buyItem is null when buying is off. */
record Settings(int single, int dbl, int quad, int[] multipliers, int maxUpgrades, float viewRange,
        Material buyItem, int buyAmount) {

    static Settings from(FileConfiguration c) {
        List<Integer> m = c.getIntegerList("upgrade-multipliers");
        int[] multipliers = m.size() == 5
                ? m.stream().mapToInt(Integer::intValue).toArray()
                : new int[] {2, 4, 8, 16, 32};
        Material buyItem = Material.matchMaterial(c.getString("buy.item", "iron_ingot"));
        int buyAmount = c.getInt("buy.amount", 3);
        if (buyItem == null || !buyItem.isItem() || buyItem.isAir() || buyAmount <= 0) {
            buyItem = null;
        }
        return new Settings(
                Math.max(1, c.getInt("base-stacks.single", 32)),
                Math.max(1, c.getInt("base-stacks.double", 16)),
                Math.max(1, c.getInt("base-stacks.quad", 8)),
                multipliers,
                Math.max(0, Math.min(7, c.getInt("max-upgrades", 7))),
                (float) c.getDouble("view-range", 0.25),
                buyItem,
                Math.max(1, Math.min(64 * 36, buyAmount)));
    }

    long baseStacks(int slots) {
        return switch (slots) {
            case 2 -> dbl;
            case 4 -> quad;
            default -> single;
        };
    }

    /** Multiplier of one upgrade tier, 0 for anything unknown. */
    int multiplier(int tier) {
        return tier >= 1 && tier <= multipliers.length ? multipliers[tier - 1] : 0;
    }
}
