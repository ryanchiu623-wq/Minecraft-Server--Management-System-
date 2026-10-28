package tw.ryanchiu.panelkey;

import java.nio.charset.StandardCharsets;
import java.util.Locale;
import java.util.Set;
import java.util.UUID;

import org.bukkit.Bukkit;
import org.bukkit.entity.Player;
import org.bukkit.event.EventHandler;
import org.bukkit.event.EventPriority;
import org.bukkit.event.Listener;
import org.bukkit.event.player.PlayerCommandPreprocessEvent;
import org.bukkit.event.player.PlayerJoinEvent;

/**
 * Hands QualityArmory's gun resource pack to admins only.
 *
 * QualityArmory either offers its pack to everyone on join (sendOnJoin) or to
 * nobody. Its /qa commands do not help: "getResourcepack" only posts the
 * download link in chat and "sendResourcepack" only puts the player back on
 * the join list - neither offers the pack, and neither checks a permission.
 * So sendOnJoin is off in its config, this offers the pack itself to players
 * with the permission when they join, and refuses those two subcommands to
 * everyone else.
 */
final class GunPack implements Listener {

    /** QualityArmory subcommands that hand out its pack. */
    private static final Set<String> PACK_SUBCOMMANDS = Set.of("getresourcepack", "sendresourcepack");
    private static final Set<String> QA_LABELS = Set.of("qa", "qualityarmory");
    /** Fixed, so a rejoin replaces the pack instead of stacking a second copy. */
    private static final UUID PACK_ID = UUID.nameUUIDFromBytes("panelkey-gun-pack".getBytes(StandardCharsets.UTF_8));

    private final PanelKey plugin;
    private final String url;
    private final String permission;
    private final long delayTicks;

    GunPack(PanelKey plugin, String url, String permission, double delaySeconds) {
        this.plugin = plugin;
        this.url = url;
        this.permission = permission;
        this.delayTicks = Math.max(0L, Math.round(delaySeconds * 20));
    }

    @EventHandler(priority = EventPriority.MONITOR)
    public void onJoin(PlayerJoinEvent event) {
        Player player = event.getPlayer();
        if (!player.hasPermission(permission)) {
            return;
        }
        // A pack offered while the client is still loading the world can be
        // dropped, which is why QualityArmory waits too (SecondsTillRPIsSent).
        Bukkit.getScheduler().runTaskLater(plugin, () -> {
            if (!player.isOnline()) {
                return;
            }
            // No hash: the pack is QualityArmory's "latest" release, so its
            // hash changes whenever they publish one.
            player.addResourcePack(PACK_ID, url, null, "槍械材質包（只給管理員）", false);
            plugin.getLogger().info("Offered the gun pack to " + player.getName());
        }, delayTicks);
    }

    // LOWEST so QualityArmory never sees a refused request.
    @EventHandler(priority = EventPriority.LOWEST, ignoreCancelled = true)
    public void onCommand(PlayerCommandPreprocessEvent event) {
        String[] words = event.getMessage().substring(1).toLowerCase(Locale.ROOT).split("\\s+");
        if (words.length < 2) {
            return;
        }
        String label = words[0].substring(words[0].indexOf(':') + 1);
        if (!QA_LABELS.contains(label) || !PACK_SUBCOMMANDS.contains(words[1])) {
            return;
        }
        if (event.getPlayer().hasPermission(permission)) {
            return;
        }
        event.setCancelled(true);
        event.getPlayer().sendMessage("槍械材質包只開放給管理員。");
    }
}
