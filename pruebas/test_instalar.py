import os

from audiotrans import instalar


def test_skill_enlaza_para_todos_los_agentes(tmp_path):
    (tmp_path / ".claude").mkdir()  # Claude Code y agy instalados; Grok no
    (tmp_path / ".gemini" / "antigravity-cli").mkdir(parents=True)
    instalar.skill(str(tmp_path))
    comun = tmp_path / ".agents" / "skills" / "traducir-episodio"
    assert os.readlink(comun) == os.path.join(instalar.PAQUETE, "skills", "traducir-episodio")
    assert (comun / "SKILL.md").read_text().startswith("---\nname: traducir-episodio\n")
    assert os.readlink(tmp_path / ".claude" / "skills" / "traducir-episodio") == "../../.agents/skills/traducir-episodio"
    assert (tmp_path / ".claude" / "skills" / "traducir-episodio" / "SKILL.md").exists()
    assert os.readlink(tmp_path / ".gemini" / "config" / "skills" / "traducir-episodio") == "../../../.agents/skills/traducir-episodio"
    assert (tmp_path / ".gemini" / "config" / "skills" / "traducir-episodio" / "SKILL.md").exists()
    assert not (tmp_path / ".grok").exists()
    assert not (tmp_path / ".gemini" / "skills").exists()  # Gemini CLI avisaría de un conflicto
    instalar.skill(str(tmp_path))  # se puede volver a correr
    assert (comun / "SKILL.md").exists()


def test_skill_no_toca_una_propia(tmp_path):
    propia = tmp_path / ".agents" / "skills" / "traducir-episodio"
    propia.mkdir(parents=True)
    (propia / "SKILL.md").write_text("mía")
    instalar.skill(str(tmp_path))
    assert (propia / "SKILL.md").read_text() == "mía"


def test_completado(tmp_path, monkeypatch):
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    instalar.completado(str(tmp_path))
    instalar.completado(str(tmp_path))  # se puede volver a correr
    enlace = tmp_path / ".local" / "share" / "bash-completion" / "completions" / "practice"
    assert "complete -o filenames -F _practice practice" in enlace.read_text()


def test_completado_solo_videos_y_carpetas(tmp_path):
    import subprocess
    for nombre in ("s1-e2.mp4", "s1-e2.srt", "s1-e2.es.tsv", "S1-E3.MKV", "tt1358522"):
        (tmp_path / nombre).write_text("")
    (tmp_path / "s1-extras").mkdir()
    script = os.path.join(instalar.PAQUETE, "completado", "practice")

    def completar(*palabras):
        r = subprocess.run(["bash", "-c", f'source "{script}"; COMP_WORDS=("$@"); COMP_CWORD=$(( $# - 1 )); '
                            '_practice; printf "%s\\n" "${COMPREPLY[@]}"', "_", "practice", *palabras],
                           cwd=tmp_path, capture_output=True, text=True, check=True)
        return sorted(r.stdout.split())

    assert completar("s1-e2.") == ["s1-e2.mp4"]
    assert completar("s") == ["s1-e2.mp4", "s1-extras", "saved"]
    assert completar("S") == ["S1-E3.MKV"]  # la extensión no distingue mayúsculas
    assert completar("s1-e2.mp4", "s1-e2.") == ["s1-e2.mp4", "s1-e2.srt"]  # otro .srt después del video
    assert completar("--translate", "s1-e2.mp4", "--agent", "c") == ["claude", "codex"]
