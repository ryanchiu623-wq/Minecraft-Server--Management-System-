package tw.ryanchiu.drawers;

import java.util.ArrayList;
import java.util.List;

import org.bukkit.Material;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.persistence.PersistentDataContainer;
import org.bukkit.persistence.PersistentDataType;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;
import net.kyori.adventure.text.format.TextColor;
import net.kyori.adventure.text.format.TextDecoration;

/** Drawer and upgrade items. */
final class Items {

    /** Index = tier - 1. */
    static final Material[] TIER_MATERIALS = {
            Material.OBSIDIAN, Material.IRON_INGOT, Material.GOLD_INGOT, Material.DIAMOND, Material.EMERALD};
    static final String[] TIER_NAMES = {"黑曜石", "鐵", "金", "鑽石", "綠寶石"};
    private static final String[] ROMAN = {"I", "II", "III", "IV", "V"};

    private Items() {
    }

    static String layoutName(int slots) {
        return switch (slots) {
            case 2 -> "雙格抽屜";
            case 4 -> "四格抽屜";
            default -> "單格抽屜";
        };
    }

    static ItemStack drawer(int slots) {
        return drawer(new DrawerData(slots));
    }

    /**
     * A drawer item carrying everything the drawer held. A blank drawer
     * carries only its layout, so broken empty drawers stack with crafted ones.
     */
    static ItemStack drawer(DrawerData d) {
        ItemStack item = new ItemStack(Material.BARREL);
        ItemMeta meta = item.getItemMeta();
        meta.displayName(plain(layoutName(d.slots), NamedTextColor.YELLOW));
        List<Component> lore = new ArrayList<>();
        lore.add(plain("右鍵放入　左鍵拿一組　蹲下左鍵拿一個", NamedTextColor.GRAY));
        lore.add(plain("連點兩下右鍵：背包裡一樣的全部放進去", NamedTextColor.GRAY));
        lore.add(plain("蹲下空手右鍵：升級、鎖定", NamedTextColor.GRAY));
        PersistentDataContainer pdc = meta.getPersistentDataContainer();
        if (d.isBlank()) {
            pdc.set(Keys.SLOTS, PersistentDataType.INTEGER, d.slots);
        } else {
            lore.add(Component.empty());
            for (int i = 0; i < d.slots; i++) {
                if (d.templates[i] != null) {
                    lore.add(plain("", NamedTextColor.WHITE)
                            .append(d.templates[i].effectiveName())
                            .append(Component.text(" ×" + d.counts[i])));
                }
            }
            if (!d.upgrades.isEmpty()) {
                lore.add(plain("升級：容量 ×" + d.multiplier(), NamedTextColor.AQUA));
            }
            if (d.locked) {
                lore.add(plain("已鎖定", NamedTextColor.GOLD));
            }
            d.write(pdc, d.counts.clone());
            // One drawer full of items per item stack, like a shulker box.
            meta.setMaxStackSize(1);
        }
        meta.lore(lore);
        item.setItemMeta(meta);
        return item;
    }

    static ItemStack upgrade(int tier) {
        ItemStack item = new ItemStack(Material.PAPER);
        ItemMeta meta = item.getItemMeta();
        meta.displayName(plain("儲存升級 " + ROMAN[tier - 1] + "（" + TIER_NAMES[tier - 1] + "）",
                TextColor.color(0x55FFFF)));
        meta.lore(List.of(
                plain("抽屜容量 ×" + RyanDrawers.settings().multiplier(tier), NamedTextColor.GRAY),
                plain("拿著它對抽屜正面按右鍵就裝上", NamedTextColor.GRAY),
                plain("多個升級的倍率會加總", NamedTextColor.DARK_GRAY)));
        // Looks like its material, but stays paper so it cannot be placed.
        meta.setItemModel(TIER_MATERIALS[tier - 1].getKey());
        meta.setEnchantmentGlintOverride(true);
        meta.getPersistentDataContainer().set(Keys.UPGRADE, PersistentDataType.INTEGER, tier);
        item.setItemMeta(meta);
        return item;
    }

    /** Upgrade tier of an item, 0 if it is not an upgrade. */
    static int upgradeTier(ItemStack item) {
        if (item == null || item.isEmpty() || !item.hasItemMeta()) {
            return 0;
        }
        Integer tier = item.getItemMeta().getPersistentDataContainer()
                .get(Keys.UPGRADE, PersistentDataType.INTEGER);
        return tier != null && tier >= 1 && tier <= 5 ? tier : 0;
    }

    static boolean isDrawer(ItemStack item) {
        return item != null && item.getType() == Material.BARREL && item.hasItemMeta()
                && DrawerData.isDrawer(item.getItemMeta().getPersistentDataContainer());
    }

    static Component plain(String text, TextColor color) {
        return Component.text(text, color).decoration(TextDecoration.ITALIC, false);
    }
}
