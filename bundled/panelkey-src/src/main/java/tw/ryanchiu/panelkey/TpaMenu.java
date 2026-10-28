package tw.ryanchiu.panelkey;

import java.util.ArrayList;
import java.util.List;

import org.bukkit.Bukkit;
import org.bukkit.Material;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.Listener;
import org.bukkit.event.inventory.InventoryClickEvent;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.meta.ItemMeta;
import org.bukkit.inventory.meta.SkullMeta;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.format.NamedTextColor;

/**
 * A chest GUI listing everyone else online; clicking a head sends them an
 * EssentialsX /tpa request. Opened from the player menu (/pmenu) or /tpamenu.
 *
 * Built in code for the same reason as TargetMenu: a YAML menu cannot list
 * who happens to be online. The request itself goes through /tpa as the
 * player, so EssentialsX's permission, cooldown and accept flow all apply.
 */
public final class TpaMenu implements Listener {

    private static final Component TITLE =
            Component.text("傳送到誰身邊", NamedTextColor.DARK_GRAY);

    private final String backCommand;

    public TpaMenu(String backCommand) {
        this.backCommand = backCommand;
    }

    public void open(Player viewer) {
        List<Player> others = new ArrayList<>();
        for (Player p : Bukkit.getOnlinePlayers()) {
            if (!p.equals(viewer)) {
                others.add(p);
            }
        }
        if (others.isEmpty()) {
            viewer.sendMessage(Component.text("現在沒有其他玩家在線上", NamedTextColor.GRAY));
            return;
        }

        // One row per nine players, plus a final row for the back button.
        int rows = Math.min(5, (others.size() + 8) / 9) + 1;
        Inventory inv = Bukkit.createInventory(null, rows * 9, TITLE);

        int slot = 0;
        for (Player p : others) {
            if (slot >= (rows - 1) * 9) {
                break;
            }
            ItemStack head = new ItemStack(Material.PLAYER_HEAD);
            SkullMeta meta = (SkullMeta) head.getItemMeta();
            meta.setOwningPlayer(p);
            meta.displayName(Component.text(p.getName(), NamedTextColor.AQUA));
            meta.lore(List.of(
                    Component.text("點擊送出傳送請求", NamedTextColor.GRAY),
                    Component.text("對方按接受之後你才會過去", NamedTextColor.GRAY)));
            head.setItemMeta(meta);
            inv.setItem(slot++, head);
        }

        ItemStack back = new ItemStack(Material.ARROW);
        ItemMeta backMeta = back.getItemMeta();
        backMeta.displayName(Component.text("返回選單", NamedTextColor.YELLOW));
        back.setItemMeta(backMeta);
        inv.setItem(rows * 9 - 1, back);

        viewer.openInventory(inv);
    }

    @EventHandler
    public void onClick(InventoryClickEvent event) {
        if (!TITLE.equals(event.getView().title())) {
            return;
        }
        // It is a menu, not a container: nothing may be taken out of it.
        event.setCancelled(true);

        if (!(event.getWhoClicked() instanceof Player viewer)) {
            return;
        }
        ItemStack clicked = event.getCurrentItem();
        if (clicked == null || !clicked.hasItemMeta()) {
            return;
        }

        if (clicked.getType() == Material.ARROW) {
            viewer.closeInventory();
            // DeluxeMenus open commands only resolve from the console.
            Bukkit.dispatchCommand(Bukkit.getConsoleSender(),
                    backCommand.replace("%player%", viewer.getName()));
            return;
        }
        if (clicked.getType() != Material.PLAYER_HEAD) {
            return;
        }
        SkullMeta meta = (SkullMeta) clicked.getItemMeta();
        String name = meta.getOwningPlayer() != null ? meta.getOwningPlayer().getName() : null;
        if (name == null) {
            return;
        }
        viewer.closeInventory();
        // As the player, so EssentialsX checks their own essentials.tpa.
        viewer.performCommand("tpa " + name);
    }
}
