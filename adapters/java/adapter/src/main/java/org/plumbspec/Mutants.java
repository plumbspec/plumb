package org.plumbspec;

import com.sun.source.tree.*;
import com.sun.source.util.*;

import javax.tools.*;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;

/**
 * Chapter 4's operators for Java: a minimal in-house AST mutation (`dev07-2-3`).
 *
 * Three source mutations — flip a comparison, negate a branch, swap a return — applied to the
 * tree the **JDK's own compiler** produces. `com.sun.source` is to Java what `ast` is to Python:
 * the language's own parser, already installed, with no PIT to take a version on. Same principle
 * as the JDWP observer, for the same reason.
 *
 * The edit is **positional, not a re-print**. Python can `ast.unparse` a mutated tree because the
 * result only has to run; here the file is recompiled in place, so a pretty-printer would rewrite
 * every line it touched and turn a one-token change into an unreadable diff for anyone who looked
 * at the tree mid-run. A mutant is the original source with exactly one span replaced.
 *
 * Nothing here compiles or runs anything — see {@link Mutation}.
 */
public final class Mutants {

    public static final String FLIP_COMPARISON = "flip-comparison";
    public static final String NEGATE_BRANCH = "negate-branch";
    public static final String SWAP_RETURN = "swap-return";

    /** The whole set (`dev07-2-3`), and the same three the Python adapter applies. */
    public static final List<String> OPERATORS =
            java.util.Arrays.asList(FLIP_COMPARISON, NEGATE_BRANCH, SWAP_RETURN);

    /** One mutated rendering of a file, and where the change was made. */
    public static final class Mutant {
        private final String operator, where, source;
        private final long line;

        public Mutant(String operator, String where, long line, String source) {
            this.operator = operator; this.where = where; this.line = line; this.source = source;
        }

        public String operator() { return operator; }
        public String where() { return where; }
        public long line() { return line; }
        public String source() { return source; }
    }

    /** Each comparison and its negation — never a neighbour, which survives on the boundary case
     *  a test is most likely to use (`dev07-2-4`). */
    private static final Map<Tree.Kind, String[]> COMPARISONS = new java.util.HashMap<Tree.Kind, String[]>();
    static {
        COMPARISONS.put(Tree.Kind.EQUAL_TO,           new String[]{"==", "!="});
        COMPARISONS.put(Tree.Kind.NOT_EQUAL_TO,       new String[]{"!=", "=="});
        COMPARISONS.put(Tree.Kind.LESS_THAN,          new String[]{"<",  ">="});
        COMPARISONS.put(Tree.Kind.GREATER_THAN_EQUAL, new String[]{">=", "<"});
        COMPARISONS.put(Tree.Kind.GREATER_THAN,       new String[]{">",  "<="});
        COMPARISONS.put(Tree.Kind.LESS_THAN_EQUAL,    new String[]{"<=", ">"});
    }

    private static final Set<String> NUMERIC =
            new java.util.HashSet<String>(java.util.Arrays.asList(
                    "int", "long", "short", "byte", "char", "float", "double"));

    /** One replacement: source[from,to) becomes text. */
    private static final class Site {
        private final String operator, where, text;
        private final long line;
        private final int from, to;

        Site(String operator, String where, long line, int from, int to, String text) {
            this.operator = operator; this.where = where; this.line = line;
            this.from = from; this.to = to; this.text = text;
        }

        String operator() { return operator; }
        String where() { return where; }
        long line() { return line; }
        int from() { return from; }
        int to() { return to; }
        String text() { return text; }
    }

    private Mutants() { }

    /**
     * Every mutant of {@code file} within the named methods, one site at a time.
     *
     * {@code scope} holds {@code Class#method} names exactly as the JVM reports them, because
     * they arrive from the observer, which reads them off live frames. A name this cannot match
     * is a method that can never be mutated, so the two spellings have to be the same one.
     */
    public static List<Mutant> of(Path file, Set<String> scope) throws IOException {
        String source = Text.read(file);
        List<Site> sites = sites(file, source, scope);
        List<Mutant> found = new ArrayList<>(sites.size());
        for (Site site : sites) {
            found.add(new Mutant(site.operator(), site.where(), site.line(),
                    source.substring(0, site.from()) + reached(site.text())
                            + source.substring(site.to())));
        }
        return found;
    }

    /**
     * The mutated expression, wrapped so the run can say whether it was ever evaluated (`dev07-2-4`).
     *
     * <p>A survivor nobody reached is not a weak test. A method is scoped whole, so a story whose
     * test sends one kind of event gets mutants on the guard clauses for every other kind — lines
     * it never enters, and mutants it could not kill however good it were. Reporting those beside
     * real gaps sends a reader to strengthen a test against code it was never going to run.
     *
     * <p>{@code PlumbFlag.hit} returns its argument and records that it was called, so the mutant's
     * behaviour is what it would have been: exactly one call, on exactly the line in question, and
     * no coverage tool taken on (`dev07-1-3`). Unlike equivalence — undecidable, and open as `dev07-2-4` —
     * this is a fact the run can simply observe.
     */
    private static String reached(String mutation) {
        return "org.plumbspec.PlumbFlag.hit(" + mutation + ")";
    }

    /** How many mutants {@link #of} would yield, without building any of their sources —
     *  a cost estimate that costs as much as the run is not an estimate (`dev07-2-2`). */
    public static int count(Path file, Set<String> scope) throws IOException {
        return sites(file, Text.read(file), scope).size();
    }

    private static List<Site> sites(Path file, String source, Set<String> scope) throws IOException {
        JavaCompiler compiler = ToolProvider.getSystemJavaCompiler();
        try (StandardJavaFileManager files = compiler.getStandardFileManager(null, null, null)) {
            JavacTask task = (JavacTask) compiler.getTask(
                    null, files, diagnostic -> { }, java.util.Collections.emptyList(), null,
                    files.getJavaFileObjects(file.toFile()));
            CompilationUnitTree unit = task.parse().iterator().next();
            Collector collector = new Collector(
                    unit, Trees.instance(task).getSourcePositions(), source, scope);
            collector.scan(unit, null);
            return collector.found;
        }
    }

    /** Walks the tree carrying just enough context to know where it is and what may be returned. */
    private static final class Collector extends TreeScanner<Void, Void> {

        private final CompilationUnitTree unit;
        private final SourcePositions positions;
        private final String source;
        private final Set<String> scope;
        private final List<Site> found = new ArrayList<>();
        private final Deque<String> classes = new ArrayDeque<>();
        private String method;
        private String returns;

        Collector(CompilationUnitTree unit, SourcePositions positions, String source,
                  Set<String> scope) {
            this.unit = unit;
            this.positions = positions;
            this.source = source;
            this.scope = scope;
        }

        @Override
        public Void visitClass(ClassTree node, Void ignored) {
            // `Outer$Inner`, matching what the JVM calls it — the observer's names come from live
            // frames, and a name that does not match is a method that can never be scoped in.
            String prefix = classes.isEmpty()
                    ? (unit.getPackageName() == null ? "" : unit.getPackageName() + ".")
                    : classes.peek() + "$";
            classes.push(prefix + node.getSimpleName());
            try {
                return super.visitClass(node, ignored);
            } finally {
                classes.pop();
            }
        }

        @Override
        public Void visitMethod(MethodTree node, Void ignored) {
            String outer = method, outerReturns = returns;
            method = node.getName().toString();
            returns = node.getReturnType() == null ? null : node.getReturnType().toString();
            try {
                return inScope() ? super.visitMethod(node, ignored) : null;
            } finally {
                method = outer;
                returns = outerReturns;
            }
        }

        private boolean inScope() {
            return method != null && !classes.isEmpty()
                    && scope.contains(Name.of(classes.peek(), method));
        }

        @Override
        public Void visitBinary(BinaryTree node, Void ignored) {
            String[] pair = COMPARISONS.get(node.getKind());
            if (pair != null && inScope()) {
                // The operator token is whatever sits between the two operands. Searching that gap
                // for the operator we already know is there cannot collide with anything else.
                int leftEnd = (int) positions.getEndPosition(unit, node.getLeftOperand());
                int rightStart = (int) positions.getStartPosition(unit, node.getRightOperand());
                int at = source.indexOf(pair[0], leftEnd);
                int from = (int) positions.getStartPosition(unit, node);
                int to = (int) positions.getEndPosition(unit, node);
                if (at >= 0 && at < rightStart && from >= 0 && to > from && at >= from) {
                    // THE WHOLE COMPARISON, not the operator token alone. The token is what
                    // changes, but the probe that says whether this mutant was ever reached has to
                    // wrap an expression, and `>=` is not one. Rebuilt around the new operator so
                    // the recorded text is still exactly the mutated source.
                    add(FLIP_COMPARISON, from, to,
                            source.substring(from, at) + pair[1]
                                    + source.substring(at + pair[0].length(), to));
                }
            }
            return super.visitBinary(node, ignored);
        }

        @Override
        public Void visitIf(IfTree node, Void ignored) {
            negate(node.getCondition());
            return super.visitIf(node, ignored);
        }

        @Override
        public Void visitWhileLoop(WhileLoopTree node, Void ignored) {
            negate(node.getCondition());
            return super.visitWhileLoop(node, ignored);
        }

        /** Wrap the condition's *inner* expression: `if` keeps its own parentheses, so negating
         *  the parenthesized tree itself would produce `if !(x)` and fail to compile. */
        private void negate(ExpressionTree condition) {
            if (!inScope()) return;
            ExpressionTree inner = condition instanceof ParenthesizedTree
                    ? ((ParenthesizedTree) condition).getExpression() : condition;
            int from = (int) positions.getStartPosition(unit, inner);
            int to = (int) positions.getEndPosition(unit, inner);
            if (from >= 0 && to > from) add(NEGATE_BRANCH, from, to, "!(" + source.substring(from, to) + ")");
        }

        @Override
        public Void visitReturn(ReturnTree node, Void ignored) {
            if (node.getExpression() != null && inScope()) {
                int from = (int) positions.getStartPosition(unit, node.getExpression());
                int to = (int) positions.getEndPosition(unit, node.getExpression());
                if (from >= 0 && to > from) add(SWAP_RETURN, from, to, swapped(source.substring(from, to)));
            }
            return super.visitReturn(node, ignored);
        }

        /**
         * A different value of the same type, read off the method's *declared* return type.
         *
         * Syntactic on purpose: the declared type is right there in the tree, so this needs no
         * attribution pass and works on a file that does not currently compile against its
         * dependencies. Java's typing is what forces the question at all — Python can return
         * `None` from anything, and here that would not compile, which is a mutant that proves
         * nothing about the test.
         */
        private String swapped(String expression) {
            if ("boolean".equals(returns)) return "!(" + expression + ")";
            // The cast matters for the narrow types: `char + 1` is an `int`, and a mutant that
            // fails to compile has told you nothing about the test.
            if (NUMERIC.contains(returns)) return "(" + returns + ")((" + expression + ") + 1)";
            return "null";
        }

        /**
         * Record a site, unless the mutation would change nothing.
         *
         * <p><b>An identity mutant is worse than a missing one.</b> `swap-return` on `return null;`
         * replaces `null` with `null` — the mutated source is byte-identical, it compiles, it runs,
         * and no test can possibly notice it. So it is counted as a survivor forever, capping the
         * story's ratio below 100% however strong the tests get, and sending the reader to hunt for
         * an assertion that cannot exist. Found by an adopter chasing survivors by name, with a
         * `diff` on two of them.
         *
         * <p>Checked as *output equals input*, rather than by special-casing `return null`. That is
         * the property that makes a mutant unkillable, and any operator can have it — the narrow
         * fix would leave the next one to be discovered the same expensive way.
         */
        private void add(String operator, int from, int to, String text) {
            // On the RAW mutation, before the reach probe is wrapped around it: every wrapped text
            // differs from its original, so checking the emitted form would make this test pass
            // always and let identity mutants back in.
            if (text.equals(source.substring(from, to))) return;
            found.add(new Site(operator, Name.of(classes.peek(), method),
                    unit.getLineMap().getLineNumber(from), from, to, text));
        }
    }
}
