package tw.ryanchiu.drawers;

import java.util.List;

import org.bukkit.configuration.file.FileConfiguration;

/** config.yml, read once on enable. */
record Settings(int single, int dbl, int quad, int[] multipliers, int maxUpgrades, float viewRange) {

    static Settings from(FileConfiguration c) {
        List<Integer> m = c.getIntegerList("upgrade-multipliers");
        int[] multipliers = m.size() == 5
                ? m.stream().mapToInt(Integer::intValue).toArray()
                : new int[] {2, 4, 8, 16, 32};
        return new Settings(
                Math.max(1, c.getInt("base-stacks.single", 32)),
                Math.max(1, c.getInt("base-stacks.double", 16)),
                Math.max(1, c.getInt("base-stacks.quad", 8)),
                multipliers,
                Math.max(0, Math.min(7, c.getInt("max-upgrades", 7))),
                (float) c.getDouble("view-range", 0.25));
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
