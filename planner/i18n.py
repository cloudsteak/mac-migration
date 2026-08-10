"""i18n strings for migration plan generator."""

from __future__ import annotations

PLAN_MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        "title": "# macOS Migration Plan",
        "intro": (
            "Review and check off each item before migrating. "
            "Generated from collector inventory + folder analysis."
        ),
        "section_copy": "## Copy 1:1 to external drive",
        "section_reinstall": "## Reinstall (app will recreate data)",
        "section_rebuild": "## Rebuild consciously (configs, dotfiles, dev stack)",
        "section_skip": "## Skip (cache / temp)",
        "section_review": "## Manual review required",
        "section_auth": "## Re-authenticate on new Mac",
        "item_copy": "- [ ] `{path}` ({size}) — {reason}",
        "item_reinstall": "- [ ] Reinstall: **{name}** ({source})",
        "item_rebuild_brew": "- [ ] Restore Homebrew: `./mac-migration restore homebrew`",
        "item_rebuild_dotfiles": "- [ ] Review dotfiles listed in `05-configs-dotfiles.md`",
        "item_rebuild_runtimes": "- [ ] Reinstall version managers (pyenv, nvm, etc.) from `03-version-managers.md`",
        "section_restore_auto": "## Automatic restore (one command on new Mac)",
        "item_restore_auto": "- [ ] Run `bash ~/migration-inventory/restore.sh` — restores: {components}",
        "item_restore_dry_run": "- [ ] Preview first: `./mac-migration restore all --dry-run`",
        "item_skip": "- [ ] Skip: `{path}` ({size}) — {reason}",
        "item_app_data_note": "- [ ] App data (reinstall): `{path}` ({size}) — {reason}",
        "item_review": "- [ ] Review: `{path}` ({size}) — {reason}",
        "item_auth_ssh": "- [ ] Copy `~/.ssh` securely (or regenerate keys and update remotes)",
        "item_auth_gpg": "- [ ] Migrate GPG keys if used",
        "item_auth_cloud": "- [ ] Re-run `gcloud auth login` / `aws configure` / Azure CLI login",
        "item_auth_git": "- [ ] Verify git identity and credential helper on new Mac",
        "summary": "## Summary",
        "summary_counts": "- Copy: {copy} | Reinstall-related: {app} | Skip: {skip} | Review: {review}",
        "lang_link_en": "> **Language:** English | [Magyar]({other})",
        "lang_link_hu": "> **Nyelv:** [English]({other}) | Magyar",
        "done": "Done: {path}",
        "input_analysis_missing": "ERROR: analysis JSON not found: {path}",
        "input_collector_missing": "ERROR: collector JSON not found: {path}",
    },
    "hu": {
        "title": "# macOS migrációs terv",
        "intro": (
            "Minden sort ellenőrizz és pipálj ki az átállás előtt. "
            "A collector leltár + mappa-elemzés alapján generálva."
        ),
        "section_copy": "## Áthozni 1:1 (külső meghajtóra)",
        "section_reinstall": "## Újratelepíteni (az app újra létrehozza az adatot)",
        "section_rebuild": "## Újraépíteni tudatosan (config, dotfile, dev stack)",
        "section_skip": "## Kihagyni (cache / ideiglenes)",
        "section_review": "## Kézi ellenőrzés szükséges",
        "section_auth": "## Újra-authentikálni az új Mac-en",
        "item_copy": "- [ ] `{path}` ({size}) — {reason}",
        "item_reinstall": "- [ ] Újratelepítés: **{name}** ({source})",
        "item_rebuild_brew": "- [ ] Homebrew visszaállítás: `./mac-migration restore homebrew`",
        "item_rebuild_dotfiles": "- [ ] Dotfile-ok átnézése: `05-configs-dotfiles.md`",
        "item_rebuild_runtimes": "- [ ] Verziókezelő runtime-ok (pyenv, nvm stb.): `03-version-managers.md`",
        "section_restore_auto": "## Automatikus visszaállítás (egy parancs az új Mac-en)",
        "item_restore_auto": "- [ ] Futtasd: `bash ~/migration-inventory/restore.sh` — visszaállítja: {components}",
        "item_restore_dry_run": "- [ ] Előnézet: `./mac-migration restore all --dry-run`",
        "item_skip": "- [ ] Kihagyás: `{path}` ({size}) — {reason}",
        "item_app_data_note": "- [ ] App-adat (újratelepítés): `{path}` ({size}) — {reason}",
        "item_review": "- [ ] Ellenőrizni: `{path}` ({size}) — {reason}",
        "item_auth_ssh": "- [ ] `~/.ssh` biztonságos átvitele (vagy új kulcsok + remote frissítés)",
        "item_auth_gpg": "- [ ] GPG kulcsok migrálása, ha használod",
        "item_auth_cloud": "- [ ] `gcloud auth login` / `aws configure` / Azure CLI bejelentkezés",
        "item_auth_git": "- [ ] Git identitás és credential helper ellenőrzése az új Mac-en",
        "summary": "## Összegzés",
        "summary_counts": "- Másolandó: {copy} | App-adat (újratelepítés): {app} | Kihagyható: {skip} | Ellenőrizendő: {review}",
        "lang_link_en": "> **Language:** English | [Magyar]({other})",
        "lang_link_hu": "> **Nyelv:** [English]({other}) | Magyar",
        "done": "==> Kész: {path}",
        "input_analysis_missing": "HIBA: elemzés JSON nem található: {path}",
        "input_collector_missing": "HIBA: collector JSON nem található: {path}",
    },
}


def pt(lang: str, key: str, **kwargs: str | int) -> str:
    msgs = PLAN_MESSAGES.get(lang, PLAN_MESSAGES["en"])
    msg = msgs[key]
    return msg.format(**kwargs) if kwargs else msg
