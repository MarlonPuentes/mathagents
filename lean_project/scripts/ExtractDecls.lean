/-
  Extrae los teoremas de Mathlib a un archivo JSON Lines para el índice de embeddings.
  Uso (desde lean_project/):
    lake env lean --run scripts/ExtractDecls.lean <Modulo> <salida.jsonl> [prefijo1 prefijo2 ...]
  Ejemplo:
    lake env lean --run scripts/ExtractDecls.lean Mathlib ../retrieval/mathlib_decls.jsonl Mathlib.Algebra Mathlib.NumberTheory
  Cada línea: {"name": ..., "statement": ..., "module": ...}
-/
import Lean
open Lean Meta

def ppType (env : Environment) (ty : Expr) : IO String := do
  let ctx : Core.Context := { fileName := "<extract>", fileMap := default, maxHeartbeats := 0 }
  let st : Core.State := { env := env }
  let (fmt, _) ← (MetaM.run' (ppExpr ty)).toIO ctx st
  return (fmt.pretty 100000).replace "\n" " "

def wanted (modName : Name) (prefixes : List String) : Bool :=
  prefixes.isEmpty || prefixes.any (fun p => p.isPrefixOf modName.toString)

unsafe def main (args : List String) : IO UInt32 := do
  match args with
  | modStr :: outPath :: prefixes =>
    initSearchPath (← findSysroot)
    let modName := modStr.toName
    enableInitializersExecution
    let env ← importModules #[{ module := modName }] {} (trustLevel := 1024) (loadExts := true)
    let out ← IO.FS.Handle.mk outPath IO.FS.Mode.write
    let mut count : Nat := 0
    let mut failed : Nat := 0
    for (n, ci) in env.constants.map₁.toList do
      let .thmInfo _ := ci | continue
      if n.isInternal then continue
      let some idx := env.getModuleIdxFor? n | continue
      let m := env.header.moduleNames[idx.toNat]!
      if !wanted m prefixes then continue
      try
        let stmt ← ppType env ci.type
        let j := Json.mkObj [("name", toJson n.toString), ("statement", toJson stmt),
                             ("module", toJson m.toString)]
        out.putStrLn j.compress
        count := count + 1
      catch _ =>
        failed := failed + 1
    IO.println s!"Extraídos {count} teoremas ({failed} fallaron al imprimirse) -> {outPath}"
    return 0
  | _ =>
    IO.eprintln "Uso: lake env lean --run scripts/ExtractDecls.lean <Modulo> <salida.jsonl> [prefijos...]"
    return 1
