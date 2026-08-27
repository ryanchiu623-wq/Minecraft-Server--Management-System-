package tw.ryanchiu.panelkey;

import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;

import org.bukkit.entity.Player;

/**
 * Remembers who each admin is currently handing items to.
 *
 * The toolbox menu is a static YAML file, so it cannot hold per-player state.
 * Instead it asks for the placeholder %panelkey_target%, and this class is
 * what answers - defaulting to the player themselves when nothing is chosen.
 */
public final class TargetStore {

    private final Map<UUID, String> targets = new ConcurrentHashMap<>();

    /** Name the given player's items should go to. Never null. */
    public String resolve(Player player) {
        String chosen = targets.get(player.getUniqueId());
        return chosen != null ? chosen : player.getName();
    }

    public void set(Player player, String targetName) {
        targets.put(player.getUniqueId(), targetName);
    }

    /** Back to giving to yourself. */
    public void clear(Player player) {
        targets.remove(player.getUniqueId());
    }

    public boolean isSelf(Player player) {
        String chosen = targets.get(player.getUniqueId());
        return chosen == null || chosen.equalsIgnoreCase(player.getName());
    }
}
