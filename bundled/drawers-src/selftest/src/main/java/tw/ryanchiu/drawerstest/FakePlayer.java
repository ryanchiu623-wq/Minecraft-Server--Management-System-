package tw.ryanchiu.drawerstest;

import java.lang.reflect.InvocationHandler;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import java.util.TreeSet;
import java.util.UUID;

import org.bukkit.Bukkit;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.block.BlockFace;
import org.bukkit.entity.Player;
import org.bukkit.event.inventory.InventoryType;
import org.bukkit.inventory.Inventory;
import org.bukkit.inventory.InventoryView;
import org.bukkit.inventory.ItemStack;
import org.bukkit.inventory.PlayerInventory;
import org.bukkit.permissions.Permission;
import org.bukkit.util.RayTraceResult;

import net.kyori.adventure.text.Component;
import net.kyori.adventure.text.serializer.plain.PlainTextComponentSerializer;

/**
 * A Player with no client behind it: just enough of the interface for
 * RyanDrawers' listeners, everything else answers with a default and is
 * noted in {@link #unhandled} so a test can tell when the plugin started
 * relying on something new.
 *
 * The inventory is a real server inventory, so held items are live mirrors
 * exactly as they are for a real player - setAmount on the hand writes through.
 */
final class FakePlayer {

    final Player player;
    final Inventory storage = Bukkit.createInventory(null, 36);
    final PlayerInventory inventory;
    final List<String> actionBars = new ArrayList<>();
    final List<String> messages = new ArrayList<>();
    final Set<String> unhandled = new TreeSet<>();
    final Set<String> permissions = new HashSet<>();
    private final UUID id = UUID.randomUUID();
    private final ClassLoader loader;

    Location location;
    boolean sneaking;
    GameMode mode = GameMode.SURVIVAL;
    RayTraceResult aim;
    Inventory opened;
    boolean closed;
    int held;

    FakePlayer(Location location, ClassLoader loader) {
        this.location = location;
        this.loader = loader;
        player = (Player) Proxy.newProxyInstance(loader, new Class<?>[] {Player.class}, this::playerCall);
        inventory = (PlayerInventory) Proxy.newProxyInstance(loader, new Class<?>[] {PlayerInventory.class},
                this::inventoryCall);
    }

    ItemStack hand() {
        ItemStack s = storage.getItem(held);
        return s != null ? s : ItemStack.empty();
    }

    String lastActionBar() {
        return actionBars.isEmpty() ? "" : actionBars.get(actionBars.size() - 1);
    }

    String lastMessage() {
        return messages.isEmpty() ? "" : messages.get(messages.size() - 1);
    }

    private Object playerCall(Object proxy, Method method, Object[] args) {
        switch (method.getName()) {
            case "getUniqueId":
                return id;
            case "getName":
                return "DrawerTester";
            case "getInventory":
                return inventory;
            case "isSneaking":
                return sneaking;
            case "getGameMode":
                return mode;
            case "getWorld":
                return location.getWorld();
            case "getLocation":
                if (args != null && args.length == 1 && args[0] instanceof Location out) {
                    out.set(location.getX(), location.getY(), location.getZ());
                    out.setWorld(location.getWorld());
                    out.setRotation(location.getYaw(), location.getPitch());
                    return out;
                }
                return location.clone();
            case "getFacing":
                return facing(location.getYaw());
            case "rayTraceBlocks":
                return aim;
            case "sendActionBar":
                actionBars.add(plain(args[0]));
                return null;
            case "sendMessage":
                messages.add(plain(args[args.length - 1]));
                return null;
            case "openInventory":
                if (args[0] instanceof Inventory inv) {
                    opened = inv;
                    closed = false;
                }
                return null;
            case "closeInventory":
                closed = true;
                return null;
            case "hasPermission":
                return permissions.contains(args[0] instanceof Permission perm ? perm.getName() : args[0]);
            case "isOp":
                return false;
            case "discoverRecipe":
            case "isOnline":
            case "isValid":
                return true;
            case "equals":
                return proxy == args[0];
            case "hashCode":
                return System.identityHashCode(proxy);
            case "toString":
                return "FakePlayer";
            default:
                unhandled.add("Player." + method.getName());
                return defaultValue(method.getReturnType());
        }
    }

    private Object inventoryCall(Object proxy, Method method, Object[] args) throws Throwable {
        switch (method.getName()) {
            case "getItemInMainHand":
                return hand();
            case "getItemInOffHand":
                return ItemStack.empty();
            case "setItemInMainHand":
                storage.setItem(held, (ItemStack) args[0]);
                return null;
            case "getHeldItemSlot":
                return held;
            case "getHolder":
                return player;
            case "getType":
                return InventoryType.PLAYER;
            case "equals":
                return proxy == args[0];
            case "hashCode":
                return System.identityHashCode(proxy);
            case "toString":
                return "FakePlayerInventory";
            default:
                // PlayerInventory redeclares some Inventory methods (setItem...):
                // anything Inventory also has goes to the real inventory.
                Method plain;
                try {
                    plain = Inventory.class.getMethod(method.getName(), method.getParameterTypes());
                } catch (NoSuchMethodException e) {
                    plain = null;
                }
                if (plain != null) {
                    try {
                        return plain.invoke(storage, args);
                    } catch (InvocationTargetException e) {
                        throw e.getCause();
                    }
                }
                unhandled.add("PlayerInventory." + method.getName());
                return defaultValue(method.getReturnType());
        }
    }

    /** The view a click in an open menu comes from: menu on top, this player's storage below. */
    InventoryView view(Inventory top) {
        return (InventoryView) Proxy.newProxyInstance(loader, new Class<?>[] {InventoryView.class},
                (proxy, method, args) -> switch (method.getName()) {
                    case "getTopInventory" -> top;
                    case "getBottomInventory" -> storage;
                    case "getPlayer" -> player;
                    case "getInventory" -> (int) args[0] < 0 ? null : (int) args[0] < top.getSize() ? top : storage;
                    case "convertSlot" -> (int) args[0] < top.getSize() ? (int) args[0] : (int) args[0] - top.getSize();
                    case "getItem" -> slotInventory(top, (int) args[0]).getItem(local(top, (int) args[0]));
                    case "setItem" -> {
                        slotInventory(top, (int) args[0]).setItem(local(top, (int) args[0]), (ItemStack) args[1]);
                        yield null;
                    }
                    case "getSlotType" -> InventoryType.SlotType.CONTAINER;
                    case "countSlots" -> top.getSize() + storage.getSize();
                    case "getType" -> InventoryType.CHEST;
                    case "title", "originalTitle" -> Component.empty();
                    case "getTitle", "getOriginalTitle" -> "";
                    case "equals" -> proxy == args[0];
                    case "hashCode" -> System.identityHashCode(proxy);
                    case "toString" -> "FakeView";
                    default -> {
                        unhandled.add("InventoryView." + method.getName());
                        yield defaultValue(method.getReturnType());
                    }
                });
    }

    private Inventory slotInventory(Inventory top, int raw) {
        return raw < top.getSize() ? top : storage;
    }

    private static int local(Inventory top, int raw) {
        return raw < top.getSize() ? raw : raw - top.getSize();
    }

    static BlockFace facing(float yaw) {
        BlockFace[] byQuarter = {BlockFace.SOUTH, BlockFace.WEST, BlockFace.NORTH, BlockFace.EAST};
        return byQuarter[Math.floorMod(Math.round(yaw / 90f), 4)];
    }

    private static String plain(Object o) {
        return o instanceof Component c ? PlainTextComponentSerializer.plainText().serialize(c) : String.valueOf(o);
    }

    private static Object defaultValue(Class<?> type) {
        if (type == boolean.class) {
            return false;
        } else if (type == int.class) {
            return 0;
        } else if (type == long.class) {
            return 0L;
        } else if (type == double.class) {
            return 0.0;
        } else if (type == float.class) {
            return 0f;
        } else if (type == short.class) {
            return (short) 0;
        } else if (type == byte.class) {
            return (byte) 0;
        } else if (type == char.class) {
            return '\0';
        }
        return null;
    }
}
