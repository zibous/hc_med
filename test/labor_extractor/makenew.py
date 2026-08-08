from rope.base.project import Project
from rope.refactor.move import MoveGlobal

# 1. Project initialisieren
project = Project('.')
old_script_path = '../extract_labvalues.py'

# 2. Die Ziel-Module als echte Rope-Ressourcen laden
norm_mod = project.get_resource('src/extractor/core/normalization.py')
utils_mod = project.get_resource('src/extractor/core/utils.py')
det_mod = project.get_resource('src/extractor/parsers/detector.py')
free_mod = project.get_resource('src/extractor/parsers/freetext.py')
table_mod = project.get_resource('src/extractor/parsers/table.py')
csv_mod = project.get_resource('src/extractor/parsers/csv_tab.py')
kuerzel_mod = project.get_resource('src/extractor/parsers/kuerzel.py')
pdf_mod = project.get_resource('src/extractor/parsers/pdf.py')

def move_func(func_name, dest_resource):
    source_mod = project.get_resource(old_script_path)
    try:
        # Sucht das 'def funktion'
        search_str = f"def {func_name}"
        base_offset = source_mod.read().index(search_str)
        
        # Verschiebt den Offset auf den ersten Buchstaben des Funktionsnamens
        name_offset = base_offset + 4
        
        # Refactoring initialisieren
        mover = MoveGlobal(project, source_mod, name_offset)
        
        # WICHTIG: Hier übergeben wir das Ressourcen-Objekt statt eines Strings
        changes = mover.get_changes(dest_resource)
        project.do(changes)
        
        print(f"✓ {func_name} erfolgreich verschoben nach {dest_resource.path}")
    except ValueError:
        print(f"✗ Funktion {func_name} wurde in {old_script_path} nicht gefunden.")
    except Exception as e:
        print(f" Fehler bei {func_name}: {e}")

# Core verschieben
move_func('normalize_test_name', norm_mod)
move_func('normalize_unit_and_value', norm_mod)
move_func('classify_test', norm_mod)
move_func('calculate_age_at_date', utils_mod)

# Parsers verschieben
move_func('detect_format', det_mod)
move_func('parse_freetext_file', free_mod)
move_func('parse_table_format', table_mod)
move_func('parse_pivot_format', table_mod)
move_func('parse_csv_format', csv_mod)
move_func('parse_tab_format', csv_mod)
move_func('parse_simple_csv', csv_mod)
move_func('parse_kuerzel_space_format', kuerzel_mod)
move_func('parse_pdf_text_format', pdf_mod)
