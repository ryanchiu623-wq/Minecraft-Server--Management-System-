package tw.ryanchiu.panelkey;

import org.bukkit.OfflinePlayer;
import org.bukkit.entity.Player;

import me.clip.placeholderapi.expansion.PlaceholderExpansion;

/**
 * Exposes %panelkey_target% so the toolbox YAML can give items to whoever the
 * admin picked, instead of hard-coding %player_name%.
 */
public final class TargetExpansion extends PlaceholderExpansion {

    private final PanelKey plugin;
    private final TargetStore store;

    public TargetExpansion(PanelKey plugin, TargetStore store) {
        this.plugin = plugin;
        this.store = store;
    }

    @Override
    public String getIdentifier() {
        return "panelkey";
    }

    @Override
    public String getAuthor() {
        return "ryanchiu623";
    }

    @Override
    public String getVersion() {
        return plugin.getDescription().getVersion();
    }

    @Override
    public boolean persist() {
        // Survive a PlaceholderAPI reload; otherwise the toolbox would start
        // handing out items to a literal "%panelkey_target%".
        return true;
    }

    @Override
    public String onRequest(OfflinePlayer player, String params) {
        // Never return null for a known placeholder: PlaceholderAPI leaves the
        // raw %panelkey_target% in the string, and the toolbox would then run
        // "give %panelkey_target% ..." and hand the items to nobody.
        if (player == null) {
            return "";
        }
        String own = player.getName() == null ? "" : player.getName();

        if (params.equalsIgnoreCase("target")) {
            return (player instanceof Player online) ? store.resolve(online) : own;
        }
        if (params.equalsIgnoreCase("target_label")) {
            if (player instanceof Player online) {
                return store.isSelf(online) ? "你自己" : store.resolve(online);
            }
            return own;
        }
        return null;
    }
}
