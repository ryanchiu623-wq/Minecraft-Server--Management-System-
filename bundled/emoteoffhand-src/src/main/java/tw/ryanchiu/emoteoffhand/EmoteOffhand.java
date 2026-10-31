package tw.ryanchiu.emoteoffhand;

import org.geysermc.event.subscribe.Subscribe;
import org.geysermc.geyser.api.event.bedrock.ClientEmoteEvent;
import org.geysermc.geyser.api.extension.Extension;
import org.geysermc.geyser.session.GeyserSession;

/**
 * Makes a Bedrock emote act like the Java swap-hands key (F).
 *
 * Bedrock has no swap-hands key, so Bedrock players could neither open the
 * PanelKey menu (sneak + F) nor reload a QualityArmory gun (F). Geyser used
 * to map emotes to swap-hands through the "emote-offhand-workaround" option;
 * that option is gone, and ClientEmoteEvent is what replaced it. The swap
 * reaches the Java server as a real swap-hands action, so PanelKey and
 * QualityArmory see exactly what a Java player's F would send.
 *
 * The emote itself still plays.
 */
public class EmoteOffhand implements Extension {

    @Subscribe
    public void onEmote(ClientEmoteEvent event) {
        if (event.connection() instanceof GeyserSession session) {
            session.requestOffhandSwap();
        }
    }
}
