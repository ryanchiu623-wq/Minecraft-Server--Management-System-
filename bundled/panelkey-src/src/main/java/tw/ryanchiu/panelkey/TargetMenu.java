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
 * A chest GUI listing everyone online, for picking who the toolbox gives to.
 *
 * Built in code rather than as another DeluxeMenus file because the list is
 * dynamic - a YAML menu cannot enumerate who happens to be online.
 */
public final class TargetMenu implements Listener {

    private static final Component TITLE =
            Component.text("選擇要給誰", NamedTextColor.DARK_GRAY);

    private final PanelKey plugin;
    private final TargetStore store;

    public TargetMenu(PanelKey plugin, TargetStore store) {
        this.plugin = plugin;
        this.store = store;
    }

    public void open(Player viewer) {
        List<Player> online = new ArrayList<>(Bukkit.getOnlinePlayers());
        // One row per nine players, plus a final row for "give to myself".
        int rows = Math.min(5, Math.max(1, (online.size() + 8) / 9)) + 1;
        Inventory inv = Bukkit.createInventory(null, rows * 9, TITLE);

        int slot = 0;
        for (Player p : online) {
            if (slot >= (rows - 1) * 9) {
                break;
            }
            ItemStack head = new ItemStack(Material.PLAYER_HEAD);
            SkullMeta meta = (SkullMeta) head.getItemMeta();
            meta.setOwningPlayer(p);
            meta.displayName(Component.text(p.getName(), NamedTextColor.AQUA));
            List<Component> lore = new ArrayList<>();
            lore.add(Component.text("點擊後，工具箱給的東西都送給他",
                    NamedTextColor.GRAY));
            if (store.resolve(viewer).equalsIgnoreCase(p.getName())) {
                lore.add(Component.text("目前的目標", NamedTextColor.GREEN));
            }
            meta.lore(lore);
            head.setItemMeta(meta);
            inv.setItem(slot++, head);
        }

        ItemStack self = new ItemStack(Material.ARROW);
        ItemMeta selfMeta = self.getItemMeta();
        selfMeta.displayName(Component.text("給我自己", NamedTextColor.YELLOW));
        selfMeta.lore(List.of(Component.text("恢復預設：東西給自己", NamedTextColor.GRAY)));
        self.setItemMeta(selfMeta);
        inv.setItem(rows * 9 - 1, self);

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
            store.clear(viewer);
            viewer.sendMessage(Component.text("目標已恢復為你自己", NamedTextColor.YELLOW));
        } else if (clicked.getType() == Material.PLAYER_HEAD) {
            SkullMeta meta = (SkullMeta) clicked.getItemMeta();
            String name = meta.getOwningPlayer() != null
                    ? meta.getOwningPlayer().getName() : null;
            if (name == null) {
                return;
            }
            store.set(viewer, name);
            viewer.sendMessage(Component.text("之後工具箱給的東西都會送給 " + name,
                    NamedTextColor.AQUA));
        } else {
            return;
        }

        viewer.closeInventory();
        // Straight back to the toolbox so the next click gives to the new
        // target without the player having to reopen anything.
        Bukkit.dispatchCommand(Bukkit.getConsoleSender(),
                "dm open toolbox " + viewer.getName());
    }
}
