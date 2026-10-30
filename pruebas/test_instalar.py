import os

from audiotrans import instalar


def test_skill_enlaza_para_todos_los_agentes(tmp_path):
    (tmp_path / ".claude").mkdir()  # Claude Code instalado; Grok no
    instalar.skill(str(tmp_path))
    comun = tmp_path / ".agents" / "skills" / "traducir-episodio"
    assert os.readlink(comun) == os.path.join(instalar.PAQUETE, "skills", "traducir-episodio")
    assert (comun / "SKILL.md").read_text().startswith("---\nname: traducir-episodio\n")
    assert os.readlink(tmp_path / ".claude" / "skills" / "traducir-episodio") == "../../.agents/skills/traducir-episodio"
    assert (tmp_path / ".claude" / "skills" / "traducir-episodio" / "SKILL.md").exists()
    assert not (tmp_path / ".grok").exists()
    instalar.skill(str(tmp_path))  # se puede volver a correr
    assert (comun / "SKILL.md").exists()


def test_skill_no_toca_una_propia(tmp_path):
    propia = tmp_path / ".agents" / "skills" / "traducir-episodio"
    propia.mkdir(parents=True)
    (propia / "SKILL.md").write_text("mía")
    instalar.skill(str(tmp_path))
    assert (propia / "SKILL.md").read_text() == "mía"
