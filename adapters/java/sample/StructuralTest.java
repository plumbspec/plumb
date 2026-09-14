import java.nio.file.*;
import org.junit.jupiter.api.Test;
import org.plumbspec.Proves;

/** A structural rule: reads the artifact as data and never invokes it (`dev07-4-2`). */
class StructuralTest {

    @Test
    @Proves(value = "APP-4", depth = "unit")
    void theEntryPointClassIsWhereWeSayItIs() throws Exception {
        byte[] bytecode = Files.readAllBytes(Path.of("sample/target/classes/App.class"));
        assert bytecode.length > 0;
        assert (bytecode[0] & 0xFF) == 0xCA;   // the class-file magic, read as bytes
    }
}
