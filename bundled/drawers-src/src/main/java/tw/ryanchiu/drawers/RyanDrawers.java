package tw.ryanchiu.drawers;

import java.util.ArrayList;
import java.util.List;

import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.NamespacedKey;
import org.bukkit.Tag;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.RecipeChoice;
import org.bukkit.inventory.ShapedRecipe;
import org.bukkit.plugin.java.JavaPlugin;

/**
 * Drawers in the style of the Storage Drawers mod, without the mod: barrels
 * that hold a lot of one item per slot, with the item and its count floating
 * on the front.
 */
public final class RyanDrawers extends JavaPlugin {

    private static Settings settings;
    private final List<NamespacedKey> recipeKeys = new ArrayList<>();

    static Settings settings() {
        return settings;
    }

    List<NamespacedKey> recipeKeys() {
        return recipeKeys;
    }

    @Override
    public void onEnable() {
        saveDefaultConfig();
        settings = Settings.from(getConfig());

        Displays displays = new Displays();
        Drawers drawers = new Drawers(this, displays);
        DrawerMenu menu = new DrawerMenu(drawers);
        getServer().getPluginManager().registerEvents(new DrawerListener(this, drawers, menu), this);
        getServer().getPluginManager().registerEvents(menu, this);

        DrawerCommand command = new DrawerCommand(drawers);
        getCommand("drawers").setExecutor(command);
        getCommand("drawers").setTabCompleter(command);

        if (getConfig().getBoolean("recipes", true)) {
            addRecipes();
        }
        getLogger().info("Drawers ready: " + recipeKeys.size() + " recipes, base "
                + settings.single() + "/" + settings.dbl() + "/" + settings.quad() + " stacks");
    }

    @Override
    public void onDisable() {
        for (NamespacedKey key : recipeKeys) {
            Bukkit.removeRecipe(key);
        }
        recipeKeys.clear();
    }

    /** The mod's recipes: planks around chests. */
    private void addRecipes() {
        RecipeChoice planks = new RecipeChoice.MaterialChoice(Tag.PLANKS);
        drawerRecipe("drawer_single", 1, 1, planks, "PPP", "PCP", "PPP");
        drawerRecipe("drawer_double", 2, 2, planks, "PCP", "PPP", "PCP");
        drawerRecipe("drawer_quad", 4, 4, planks, "CPC", "PPP", "CPC");
        for (int tier = 1; tier <= 5; tier++) {
            NamespacedKey key = new NamespacedKey(this, "upgrade_" + tier);
            ShapedRecipe r = new ShapedRecipe(key, Items.upgrade(tier));
            r.shape("MSM", "SCS", "MSM");
            r.setIngredient('M', Items.TIER_MATERIALS[tier - 1]);
            r.setIngredient('S', Material.STICK);
            r.setIngredient('C', Material.CHEST);
            add(r);
        }
    }

    private void drawerRecipe(String name, int slots, int amount, RecipeChoice planks, String... shape) {
        ItemStack result = Items.drawer(slots);
        result.setAmount(amount);
        ShapedRecipe r = new ShapedRecipe(new NamespacedKey(this, name), result);
        r.shape(shape);
        r.setIngredient('P', planks);
        r.setIngredient('C', Material.CHEST);
        add(r);
    }

    private void add(ShapedRecipe r) {
        if (Bukkit.addRecipe(r)) {
            recipeKeys.add(r.getKey());
        } else {
            getLogger().warning("Could not add recipe " + r.getKey());
        }
    }
}
