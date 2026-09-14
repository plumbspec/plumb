package org.plumbspec;

import java.lang.instrument.ClassFileTransformer;
import java.lang.instrument.Instrumentation;
import java.security.ProtectionDomain;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Make the production code say when it ran, instead of asking the VM to watch for it (`dev07-1-3`).
 *
 * <p>Started with {@code -javaagent:plumb-java.jar=<production patterns>|<test roots>}.
 *
 * <p><b>Test classes are excluded by where they came from, not by what they are called.</b> Maven
 * puts tests in the same package tree as the code they test, so a declared surface of
 * {@code com.myapp.*} matches {@code com.myapp.FooTest} too — and every observer built on package
 * names has had to carry a correction for that, learned late and after the wrong answer had already
 * been reported. A transformer is handed the {@link ProtectionDomain}, so it can ask where the class
 * was loaded from and exclude the test roots outright. Location is the fact; the package name was
 * only ever a guess at it.
 */
public final class PlumbAgent {

    private PlumbAgent() { }

    public static void premain(String args, Instrumentation inst) { install(args, inst); }
    public static void agentmain(String args, Instrumentation inst) { install(args, inst); }

    static void install(String args, Instrumentation inst) {
        String[] halves = (args == null ? "" : args).split("\\|", -1);
        List<String> production = split(halves.length > 0 ? halves[0] : "");
        List<String> testRoots = split(halves.length > 1 ? halves[1] : "");
        List<String> entryPoints = split(halves.length > 2 ? halves[2] : "");
        // A fourth field, and it decides which advice the production surface gets: the bit
        // `inert` reads, the site name chapter 4 scopes a mutant to (`dev07-2-1`), or the call-site
        // store chapter 3 draws edges from (`dev07-1-3`). A comma-separated set rather than one word,
        // because these are independent questions and a fifth field would be a second place to
        // learn the answer.
        List<String> modes = split(halves.length > 3 ? halves[3] : "");
        boolean scoping = modes.contains("scope");
        boolean edges = modes.contains("edges");
        PlumbFlag.surface = !production.isEmpty();
        // The same declaration the weaver gets, matched against what a read names (`dev07-4-2`).
        PlumbFlag.declareProduction(production.toArray(new String[0]));
        PlumbFlag.armed = true;
        inst.addTransformer(new Surface(new Pointcut(production, testRoots, entryPoints, scoping, edges)), true);
        dispatchPrimitives(inst);
    }

    /** Where work escapes to a thread this run is not following (`dev07-1-4`). Deliberately short and
     *  fixed — the same two the observer watched.
     *
     *  <p>They are <b>retransformed</b>, not transformed. Both are loaded before any agent's
     *  premain runs — `java.lang.Thread` is loaded while the VM is starting — so a transformer
     *  registered at premain never sees them arriving and must ask for them again. Verified on
     *  Java 8 and 25: `isModifiableClass` is true for both and `retransformClasses` succeeds.
     *
     *  <p>The probe they carry is a call into `PlumbFlag`, which a bootstrap class can only resolve
     *  if the agent jar is on the bootstrap search path — `Boot-Class-Path` in its manifest. Get
     *  that wrong and every `Thread.start` in the JVM throws NoClassDefFoundError, so the failure
     *  is loud rather than a hand-off silently going unrecorded. */

    private static void dispatchPrimitives(Instrumentation inst) {
        if (!inst.isRetransformClassesSupported()) return;
        // REFUSE UNLESS THE PROBE IS ALREADY VISIBLE TO THE BOOTSTRAP LOADER. A dispatch primitive
        // is a bootstrap class, so a call it carries resolves through the bootstrap loader or not
        // at all — and "not at all" is not a missing fact, it is every `Thread.start` in the VM
        // throwing NoClassDefFoundError. Checked rather than assumed, because the way it goes wrong
        // is an install detail: the probe ships as its own jar beside the agent and something has
        // to have put it there.
        try {
            Class.forName(PlumbFlag.class.getName(), false, null);
        } catch (Throwable notOnTheBootstrapPath) {
            System.err.println("plumb: the dispatch primitives are not instrumented — the probe is "
                    + "not on the bootstrap path, so `dispatched` falls back to what an arrival "
                    + "shows on its own (dev07-1-4, dev07-1-4)");
            return;
        }
        List<Class<?>> wanted = new ArrayList<Class<?>>();
        for (String name : Pointcut.jdkClasses()) {
            try {
                Class<?> loaded = Class.forName(name);
                if (inst.isModifiableClass(loaded)) wanted.add(loaded);
            } catch (Throwable absent) {
                // A JVM without it is a JVM whose hand-offs do not go through it.
            }
        }
        if (wanted.isEmpty()) return;
        try {
            inst.retransformClasses(wanted.toArray(new Class<?>[0]));
        } catch (Throwable refused) {
            // `dispatched` degrades to what an arrival can say on its own (`dev07-1-4`): a hand-off
            // that arrives inside the window still reads `dispatched`, and one that arrives after
            // it reads `ungrounded` rather than being hedged. Never a failed run.
            System.err.println("plumb: dispatch primitives not instrumented (" + refused + ")");
        }
    }

    private static List<String> split(String csv) {
        List<String> found = new ArrayList<>();
        for (String one : csv.split(",")) if (!one.trim().isEmpty()) found.add(one.trim());
        return found;
    }

    static final class Surface implements ClassFileTransformer {
        private final Pointcut where;

        Surface(Pointcut where) { this.where = where; }

        @Override
        public byte[] transform(ClassLoader loader, String internalName, Class<?> beingRedefined,
                                ProtectionDomain domain, byte[] classfile) {
            if (internalName == null) return null;
            String name = internalName.replace('/', '.');
            if (where.skips(name, domain)) return null;
            try {
                byte[] woven = Probe.weave(classfile, where);
                if (where.reachesProject(name)) PlumbFlag.instrumented.incrementAndGet();
                return woven;
            } catch (Throwable declined) {
                // One class unwatched, never a run lost (`dev07-1-4`). Returning null leaves the
                // original bytes, and `inert` is withheld rather than guessed — see PlumbFlag.
                System.err.println("plumb: not instrumented, " + name + " (" + declined + ")");
                return null;
            }
        }
    }
}
