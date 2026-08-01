#!/bin/bash

# Controleer of het bestand pyproject.toml in de huidige map aanwezig is.
if [ ! -f "pyproject.toml" ]; then
  echo "Fout: pyproject.toml niet gevonden in de huidige map."
  exit 1
fi

# Haal het huidige versienummer uit pyproject.toml.
CURRENT_VERSION=$(grep '^version = ' pyproject.toml | sed 's/version = "//;s/"//')

# Splits het versienummer in hoofdversie, subversie en patch.
IFS='.' read -r MAJOR MINOR PATCH <<< "$CURRENT_VERSION"

# Verhoog de patchversie met één.
PATCH=$((PATCH + 1))

# Stel het nieuwe versienummer samen.
NEW_VERSION="$MAJOR.$MINOR.$PATCH"

# Vervang het oude versienummer in pyproject.toml door het nieuwe.
sed -i "s/^version = \".*\"/version = \"$NEW_VERSION\"/" pyproject.toml

echo "Versie succesvol verhoogd van $CURRENT_VERSION naar $NEW_VERSION in pyproject.toml."

# Voeg de wijzigingen toe en leg deze vast in een commit.
git commit -am "Versie verhoogd naar $NEW_VERSION"

# Maak een Git-tag aan voor de nieuwe release.
git tag "v$NEW_VERSION"

# Push de branch en de tag tegelijk naar GitHub.
git push origin main "v$NEW_VERSION"

# Geef een succesmelding weer op het scherm.
echo "Klaar! Versie $NEW_VERSION is gepusht naar GitHub en PyPI wordt geüpdatet."