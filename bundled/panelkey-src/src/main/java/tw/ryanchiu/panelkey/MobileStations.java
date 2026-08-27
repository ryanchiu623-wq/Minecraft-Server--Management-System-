package tw.ryanchiu.panelkey;

import java.util.Locale;

import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.inventory.InventoryType;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;

/**
 * Portable versions of the station blocks - a crafting table, ender chest and
 * so on that open anywhere.
 *
 * Bukkit has dedicated openers for a few of these (workbench, enchanting,
 * anvil). The rest are opened as a plain inventory of the matching type, which
 * the client renders and the server drives; a couple of station types have no
 * working virtual form at all, so unknown names are rejected rather than
 * silently opening an empty box.
 */
public final class MobileStations {

    private MobileStations() {
    }

    public static boolean open(Player player, String rawType) {
        String type = rawType.toLowerCase(Locale.ROOT);

        switch (type) {
            case "workbench":
            case "craft":
                // true = open even though the player is not standing at one
                player.openWorkbench(null, true);
                return true;
            case "enchanting":
            case "ench":
                player.openEnchanting(null, true);
                return true;
            case "anvil":
                player.openAnvil(null, true);
                return true;
            case "enderchest":
            case "ec":
                player.openInventory(player.getEnderChest());
                return true;
            case "grindstone":
                return openType(player, InventoryType.GRINDSTONE, "砂輪");
            case "stonecutter":
                return openType(player, InventoryType.STONECUTTER, "切石機");
            case "loom":
                return openType(player, InventoryType.LOOM, "織布機");
            case "cartography":
                return openType(player, InventoryType.CARTOGRAPHY, "製圖台");
            case "smithing":
                return openType(player, InventoryType.SMITHING, "鍛造台");
            default:
                player.sendMessage(Component.text("不認得的工作站：" + rawType,
                        NamedTextColor.RED));
                return false;
        }
    }

    private static boolean openType(Player player, InventoryType type, String label) {
        try {
            player.openInventory(Bukkit.createInventory(player, type,
                    Component.text("行動" + label, NamedTextColor.DARK_GRAY)));
            return true;
        } catch (Exception exc) {
            player.sendMessage(Component.text("這個版本無法虛擬開啟" + label,
                    NamedTextColor.RED));
            return false;
        }
    }
}
