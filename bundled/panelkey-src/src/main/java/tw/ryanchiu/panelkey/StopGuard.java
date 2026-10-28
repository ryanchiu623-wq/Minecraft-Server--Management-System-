package tw.ryanchiu.panelkey;

import java.util.Locale;
import java.util.Map;

import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerCommandPreprocessEvent;

/**
 * Turns /stop and /restart typed in game into the 5-minute countdown that
 * /serverctl runs. The server rules promise players that warning, but the
 * vanilla /stop and Spigot's /restart shut down at once, so an admin typing
 * them out of habit would break it.
 *
 * Only commands players type are caught. The console and RCON keep the
 * immediate stop: restart-sequence.py ends with one, and it stays there for
 * emergencies.
 */
final class StopGuard implements Listener {

    /** Command label -> the permission the real command needs. */
    private static final Map<String, String> GUARDED = Map.of(
            "stop", "minecraft.command.stop",
            "restart", "bukkit.command.restart");

    private final PanelKey plugin;
    private final ServerControl serverControl;
    private final boolean debug;

    StopGuard(PanelKey plugin, ServerControl serverControl, boolean debug) {
        this.plugin = plugin;
        this.serverControl = serverControl;
        this.debug = debug;
    }

    // LOWEST so the shutdown is called off before any other plugin acts on it.
    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onCommand(PlayerCommandPreprocessEvent event) {
        String action = guardedAction(event.getMessage());
        if (action == null) {
            return;
        }
        Player player = event.getPlayer();
        boolean allowed = player.hasPermission(GUARDED.get(action));
        if (debug) {
            plugin.getLogger().info("stop guard: " + player.getName() + " typed \""
                    + event.getMessage() + "\" -> " + action + ", permission=" + allowed);
        }
        // Without the permission the real command refuses on its own.
        if (!allowed) {
            return;
        }
        event.setCancelled(true);
        plugin.getLogger().info(player.getName() + " typed " + event.getMessage()
                + " - running the countdown instead");
        player.sendMessage("伺服器規則承諾關服前先廣播 5 分鐘，所以遊戲裡的 /" + action
                + " 會改成倒數。真的要立刻關，請從主控台下 stop。");
        serverControl.handle(player, new String[] {action});
    }

    /** "stop" or "restart" when the typed command ends up running one of them, otherwise null. */
    static String guardedAction(String message) {
        // No trim: "/ stop" is not a command the server would run either.
        String[] words = message.substring(1).toLowerCase(Locale.ROOT).split("\\s+");
        int at = 0;
        String label = bare(words[0]);
        // "/execute ... run stop" reaches the same command; follow each "run".
        while (label.equals("execute")) {
            int run = indexOf(words, "run", at + 1);
            if (run < 0 || run + 1 >= words.length) {
                return null;
            }
            at = run + 1;
            label = bare(words[at]);
        }
        return GUARDED.containsKey(label) ? label : null;
    }

    /** Drops a namespace, so minecraft:stop and bukkit:restart count too. */
    private static String bare(String word) {
        return word.substring(word.indexOf(':') + 1);
    }

    private static int indexOf(String[] words, String word, int from) {
        for (int i = from; i < words.length; i++) {
            if (words[i].equals(word)) {
                return i;
            }
        }
        return -1;
    }
}
