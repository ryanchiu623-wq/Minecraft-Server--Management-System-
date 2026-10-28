package tw.ryanchiu.drawers;

import java.util.List;
import java.util.Locale;
import java.util.stream.Stream;

import org.bukkit.Bukkit;
import org.bukkit.World;
import org.bukkit.block.Barrel;
import org.bukkit.block.Block;
import org.bukkit.block.BlockFace;
import org.bukkit.command.Command;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabExecutor;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * /drawers give - hand out drawers and upgrades.
 * /drawers place, info - build or inspect a drawer by coordinates, so it can
 * be tested over RCON with no player online.
 */
final class DrawerCommand implements TabExecutor {

    private static final List<String> KINDS =
            List.of("single", "double", "quad", "upgrade1", "upgrade2", "upgrade3", "upgrade4", "upgrade5");

    private final Drawers drawers;

    DrawerCommand(Drawers drawers) {
        this.drawers = drawers;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (args.length == 0) {
            return false;
        }
        try {
            switch (args[0].toLowerCase(Locale.ROOT)) {
                case "give" -> give(sender, args);
                case "place" -> place(sender, args);
                case "info" -> info(sender, args);
                default -> {
                    return false;
                }
            }
        } catch (IllegalArgumentException e) {
            sender.sendMessage("錯誤：" + e.getMessage());
        }
        return true;
    }

    private void give(CommandSender sender, String[] args) {
        if (args.length < 3) {
            throw new IllegalArgumentException("/drawers give <玩家> <" + String.join("|", KINDS) + "> [數量]");
        }
        Player target = Bukkit.getPlayerExact(args[1]);
        if (target == null) {
            throw new IllegalArgumentException("找不到線上玩家 " + args[1]);
        }
        String kind = args[2].toLowerCase(Locale.ROOT);
        ItemStack item = switch (kind) {
            case "single" -> Items.drawer(1);
            case "double" -> Items.drawer(2);
            case "quad" -> Items.drawer(4);
            case "upgrade1", "upgrade2", "upgrade3", "upgrade4", "upgrade5" ->
                    Items.upgrade(kind.charAt(7) - '0');
            default -> throw new IllegalArgumentException("不認得 " + args[2]);
        };
        int amount = args.length > 3 ? Integer.parseInt(args[3]) : 1;
        item.setAmount(Math.max(1, Math.min(64, amount)));
        Drawers.give(target, item);
        sender.sendMessage("已給 " + target.getName() + " " + item.getAmount() + " 個 " + kind);
    }

    private void place(CommandSender sender, String[] args) {
        if (args.length < 7) {
            throw new IllegalArgumentException("/drawers place <世界> <x> <y> <z> <1|2|4> <north|south|east|west>");
        }
        Block block = block(args);
        int slots = Integer.parseInt(args[5]);
        if (slots != 1 && slots != 2 && slots != 4) {
            throw new IllegalArgumentException("格數只能是 1、2、4");
        }
        BlockFace face = BlockFace.valueOf(args[6].toUpperCase(Locale.ROOT));
        if (!face.isCartesian() || face.getModY() != 0) {
            throw new IllegalArgumentException("方向只能是 north、south、east、west");
        }
        drawers.create(block, face, new DrawerData(slots));
        sender.sendMessage("已在 " + Displays.ownerKey(block) + " 放 " + Items.layoutName(slots) + "，面向 " + face);
    }

    private void info(CommandSender sender, String[] args) {
        if (args.length < 5) {
            throw new IllegalArgumentException("/drawers info <世界> <x> <y> <z>");
        }
        Block block = block(args);
        if (!DrawerData.isDrawer(block)) {
            sender.sendMessage(Displays.ownerKey(block) + " 不是抽屜（" + block.getType() + "）");
            return;
        }
        Barrel state = (Barrel) block.getState();
        DrawerData d = DrawerData.load(state);
        StringBuilder sb = new StringBuilder(Items.layoutName(d.slots))
                .append(" 面向 ").append(Displays.facing(block))
                .append(" 倍率 x").append(d.multiplier())
                .append(d.locked ? " 已鎖定" : "")
                .append(" 顯示實體 ").append(drawers.displays().count(block));
        for (int i = 0; i < d.slots; i++) {
            sb.append("\n  格").append(i).append(": ");
            if (d.templates[i] == null) {
                sb.append("（空）");
            } else {
                ItemStack stock = state.getSnapshotInventory().getItem(i);
                sb.append(d.templates[i].getType().getKey().getKey())
                        .append(" ").append(d.counts[i]).append(" / ").append(d.capacity(i))
                        .append("（木桶裡備貨 ").append(stock == null ? 0 : stock.getAmount()).append("）");
            }
        }
        sender.sendMessage(sb.toString());
    }

    private static Block block(String[] args) {
        World world = Bukkit.getWorld(args[1]);
        if (world == null) {
            throw new IllegalArgumentException("找不到世界 " + args[1]);
        }
        return world.getBlockAt(Integer.parseInt(args[2]), Integer.parseInt(args[3]), Integer.parseInt(args[4]));
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        Stream<String> options = switch (args.length) {
            case 1 -> Stream.of("give", "place", "info");
            case 2 -> args[0].equalsIgnoreCase("give")
                    ? Bukkit.getOnlinePlayers().stream().map(Player::getName)
                    : Bukkit.getWorlds().stream().map(World::getName);
            case 3 -> args[0].equalsIgnoreCase("give") ? KINDS.stream() : Stream.empty();
            case 6 -> args[0].equalsIgnoreCase("place") ? Stream.of("1", "2", "4") : Stream.empty();
            case 7 -> args[0].equalsIgnoreCase("place")
                    ? Stream.of("north", "south", "east", "west") : Stream.empty();
            default -> Stream.empty();
        };
        String prefix = args[args.length - 1].toLowerCase(Locale.ROOT);
        return options.filter(s -> s.toLowerCase(Locale.ROOT).startsWith(prefix)).toList();
    }
}
