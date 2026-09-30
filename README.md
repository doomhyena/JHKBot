# JHKBot

Egyszerű Discord bot Pythonban, amivel reakciók alapján lehet role-okat adni és elvenni.

- Reakció hozzáadása → a hozzá tartozó role megkapása
- Reakció eltávolítása → a role levétele
- Unicode és custom emoji-k támogatása
- Több Discord szerveren is használható
- A beállítások config.json-ban vannak
- A bot tokenje .env-ben van
- Nem használ adatbázist

## Követelmények

- Python 3.11+
- Discord bot a Developer Portalon
- A botnak Manage Roles és View Channel jogosultság kell

## Beállítás

### 1. Discord bot létrehozása

A Discord Developer Portalon hozz létre egy új alkalmazást, majd a Bot menüpontban:

- másold ki a bot tokenjét,
- kapcsold be a Message Content Intentet,
- a többi Privileged Intent nem szükséges.

A botot hívd meg a szerveredre legalább ezekkel a jogokkal:

- Manage Roles
- View Channels
- Read Message History

Az Administrator jogosultság nem szükséges.

Fontos, hogy a bot saját role-ja legyen magasabban, mint azok a role-ok, amelyeket kiosztani szeretnél.

### 2. Telepítés

```powershell
git clone <repo-url>
cd reaction-role-bot
```

Virtuális környezet létrehozása:

**Windows:**

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

**Linux / macOS:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Függőségek telepítése:

```bash
pip install -r requirements.txt
```

### 3. Token beállítása

Másold le az .env.example fájlt .env néven:

```bash
cp .env.example .env
```

Windows alatt:

```powershell
copy .env.example .env
```

Majd írd bele a bot tokenjét:

```env
DISCORD_TOKEN=a_te_tokened
```

A .env fájlt ne töltsd fel GitHubra.

## Konfiguráció

A config.json-ban adhatod meg, hogy melyik üzenethez melyik emoji milyen role-t adjon.

Példa:

```json
{
  "guilds": {
    "123456789012345678": {
      "messages": {
        "234567890123456789": {
          "description": "Érdeklődési körök",
          "roles": {
            "👍": 345678901234567890,
            "🎮": 456789012345678901,
            "🎨": 567890123456789012
          }
        }
      }
    }
  }
}
```

Az ID-k kimásolásához Discordban kapcsold be a Fejlesztői módot, majd jobb klikk az adott szerveren, üzeneten vagy role-on → ID másolása.

Custom emoji is használható, például:

```text
<:valami:123456789012345678>
```

A bot az emoji és a role ID-ja alapján dolgozik, így egy role átnevezése nem okoz problémát.

## Beállítás Discordból

A bot slash parancsokat is biztosít.

Például:

```text
/reaction-role add
```

vagy prefixszel:

```text
!reaction-role add <üzenet_id> @Role 🎮
```

Ezzel hozzáadhatsz egy emoji → role párost egy meglévő üzenethez.

További hasznos parancsok:

```text
/reaction-role remove
/reaction-role reload
```

A parancsokat a szerveren megfelelő jogosultsággal rendelkező felhasználók használhatják.

## Indítás

A virtuális környezet aktiválása után:

```bash
python bot.py
```

Ha minden rendben van, a bot bejelentkezik és elkezdi figyelni a konfigurált üzeneteket.

Leállítás:

```text
Ctrl + C
```

## Fontos

A bot csak olyan role-t tud kiosztani, amely alatta van a bot legmagasabb role-jának.

Ha nem működik a reakció:

- Ellenőrizd az üzenet és a role ID-ját.
- Nézd meg, hogy a bot látja-e az adott csatornát.
- Ellenőrizd a Manage Roles jogosultságot.
- Ellenőrizd a role-hierarchiát.

config.json módosítása után indítsd újra a botot.

A bot újraindítás után is működik a korábban beállított üzeneteken. A leállás alatt történt reakcióváltozásokat viszont nem pótolja visszamenőleg.

## Projektstruktúra

```text
reaction-role-bot/
├── bot.py
├── config.json
├── .env.example
├── .gitignore
├── requirements.txt
├── README.md
└── utils/
    ├── __init__.py
    ├── config.py
    └── emoji.py
```