package tw.ryanchiu.panelkey;

import java.io.File;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

import org.bukkit.entity.Player;

/**
 * /serverctl stop|restart|cancel - planned stops and restarts from in game.
 *
 * They go through the toolkit's restart-sequence.py, the same script the web
 * console, the desktop console and the Discord bot use, so players get the
 * 5-minute warning the server rules promise and any of those consoles can
 * see the countdown and call it off. A bare "stop" from the console would shut
 * down at once, which is why the admin panel no longer sends one.
 */
final class ServerControl {

    private static final Pattern PID = Pattern.compile("\"pid\"\\s*:\\s*(\\d+)");
    private static final Pattern MODE = Pattern.compile("\"mode\"\\s*:\\s*\"(\\w+)\"");

    private final PanelKey plugin;
    private final List<String> sequenceCommand;
    private final File serverDir;

    ServerControl(PanelKey plugin, List<String> sequenceCommand, File serverDir) {
        this.plugin = plugin;
        this.sequenceCommand = sequenceCommand;
        this.serverDir = serverDir;
    }

    void handle(Player player, String[] args) {
        String action = args.length > 0 ? args[0].toLowerCase() : "";
        switch (action) {
            case "stop", "restart" -> start(player, action);
            case "cancel" -> cancel(player);
            default -> player.sendMessage("用法：/serverctl <stop|restart|cancel>");
        }
    }

    private void start(Player player, String action) {
        String running = runningMode();
        if (running != null) {
            player.sendMessage("已經有一個" + verb(running) + "倒數在進行中；要取消請用 /serverctl cancel");
            return;
        }
        if (sequenceCommand.isEmpty()) {
            player.sendMessage("PanelKey 的 sequence-command 沒有設定，無法倒數" + verb(action) + "。");
            return;
        }

        List<String> command = new ArrayList<>(sequenceCommand);
        if (action.equals("stop")) {
            command.add("--stop");
        }
        command.addAll(List.of("--by", player.getName(),
                "--reason", "管理員" + verb(action) + "伺服器"));
        try {
            // Detached in effect: nothing reads its output and the server never
            // waits for it, so it carries on after this JVM has stopped.
            Process process = new ProcessBuilder(command)
                    .directory(serverDir)
                    .redirectOutput(ProcessBuilder.Redirect.DISCARD)
                    .redirectError(ProcessBuilder.Redirect.DISCARD)
                    .start();
            process.getOutputStream().close();
            plugin.getLogger().info(player.getName() + " started a " + action + " countdown");
            player.sendMessage("已開始 5 分鐘" + verb(action) + "倒數，遊戲裡會廣播。"
                    + "要取消：管理面板的「取消倒數」或 /serverctl cancel");
        } catch (IOException e) {
            plugin.getLogger().warning("Could not run " + command + ": " + e.getMessage());
            player.sendMessage("倒數程式啟動失敗：" + e.getMessage());
        }
    }

    private void cancel(Player player) {
        String running = runningMode();
        if (running == null) {
            player.sendMessage("目前沒有進行中的倒數");
            return;
        }
        // restart-sequence.py polls for this file and calls the countdown off.
        try {
            Files.writeString(new File(serverDir, "restart.cancel").toPath(),
                    LocalDateTime.now() + System.lineSeparator(), StandardCharsets.UTF_8);
            plugin.getLogger().info(player.getName() + " cancelled the " + running + " countdown");
            player.sendMessage("已要求取消" + verb(running) + "倒數");
        } catch (IOException e) {
            player.sendMessage("取消失敗：" + e.getMessage());
        }
    }

    /** "stop" or "restart" while a countdown is running, otherwise null. */
    private String runningMode() {
        try {
            String text = Files.readString(new File(serverDir, "restart.pending").toPath(),
                    StandardCharsets.UTF_8);
            Matcher pid = PID.matcher(text);
            // A file left by a sequence that died means nothing is running.
            if (!pid.find() || !ProcessHandle.of(Long.parseLong(pid.group(1)))
                    .map(ProcessHandle::isAlive).orElse(false)) {
                return null;
            }
            Matcher mode = MODE.matcher(text);
            return mode.find() ? mode.group(1) : "restart";
        } catch (IOException | NumberFormatException e) {
            return null;
        }
    }

    private static String verb(String action) {
        return action.equals("stop") ? "關閉" : "重啟";
    }
}
