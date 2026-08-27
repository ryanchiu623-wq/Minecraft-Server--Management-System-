package tw.ryanchiu.panelkey;

import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.World;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerSwapHandItemsEvent;
import org.bukkit.plugin.java.JavaPlugin;

/**
 * Opens the admin panel when a player presses the swap-hands key while
 * sneaking (Shift+F by default).
 *
 * A server cannot bind client keys. What it can do is watch for the few
 * vanilla actions the client reports back, and swapping hands is one of
 * them - so "sneak + swap" becomes a usable server-side shortcut. Plain F
 * is left alone so the offhand still works normally.
 *
 * The command runs from the console rather than through
 * Player#performCommand: DeluxeMenus registers its open commands
 * dynamically, and performCommand fails to resolve them (verified - it
 * returned false every time while "dm open <menu> <player>" from the
 * console worked).
 */
public final class PanelKey extends JavaPlugin implements Listener {

    private String consoleCommand;
    private String permission;
    private boolean requireSneak;
    private boolean debug;

    private final TargetStore targets = new TargetStore();
    private TargetMenu targetMenu;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        reloadSettings();
        getServer().getPluginManager().registerEvents(this, this);

        targetMenu = new TargetMenu(this, targets);
        getServer().getPluginManager().registerEvents(targetMenu, this);

        if (getServer().getPluginManager().isPluginEnabled("PlaceholderAPI")) {
            new TargetExpansion(this, targets).register();
            getLogger().info("Registered placeholder %panelkey_target%");
        } else {
            getLogger().warning("PlaceholderAPI not found - %panelkey_target% "
                    + "will not resolve and the toolbox would give to nobody.");
        }

        getLogger().info("PanelKey ready: sneak + swap-hands runs: " + consoleCommand);
    }

    private void reloadSettings() {
        reloadConfig();
        consoleCommand = getConfig().getString("console-command",
                "dm open admin_panel %player%");
        permission = getConfig().getString("permission", "serverpanel.admin");
        requireSneak = getConfig().getBoolean("require-sneak", true);
        debug = getConfig().getBoolean("debug", false);
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!(sender instanceof Player player)) {
            sender.sendMessage("這個指令只能由玩家使用。");
            return true;
        }
        // /spawn is for everyone, so it is checked before the admin
        // permission gate below applies to the other commands.
        if (command.getName().equalsIgnoreCase("spawn")) {
            World overworld = Bukkit.getWorlds().get(0);
            Location target = overworld.getSpawnLocation();
            // Read the spawn live rather than hard-coding coordinates, so
            // moving the world spawn needs no config change anywhere.
            player.teleport(target.clone().add(0.5, 0, 0.5));
            player.sendMessage("已傳送到出生點");
            return true;
        }

        if (!permission.isEmpty() && !player.hasPermission(permission)) {
            player.sendMessage("你沒有權限使用這個功能。");
            return true;
        }

        if (command.getName().equalsIgnoreCase("mobile")) {
            if (args.length == 0) {
                player.sendMessage("用法：/mobile <workbench|enderchest|anvil|"
                        + "enchanting|grindstone|stonecutter|loom|cartography|smithing>");
                return true;
            }
            MobileStations.open(player, args[0]);
            return true;
        }

        targetMenu.open(player);
        return true;
    }

    @EventHandler(priority = EventPriority.NORMAL, ignoreCancelled = true)
    public void onSwapHands(PlayerSwapHandItemsEvent event) {
        Player player = event.getPlayer();
        boolean sneaking = player.isSneaking();
        boolean allowed = permission.isEmpty() || player.hasPermission(permission);

        if (debug) {
            getLogger().info("swap-hands by " + player.getName()
                    + " sneaking=" + sneaking + " permission=" + allowed);
        }

        if (requireSneak && !sneaking) {
            return;
        }
        if (!allowed) {
            return;
        }

        // Without this the offhand item would swap as well as opening the menu.
        event.setCancelled(true);

        String toRun = consoleCommand.replace("%player%", player.getName());
        boolean ran = Bukkit.dispatchCommand(Bukkit.getConsoleSender(), toRun);
        if (debug) {
            getLogger().info("dispatched: " + toRun + " -> " + ran);
        }
    }
}
