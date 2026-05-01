import os
import shutil
import pandas as pd
import re

catalogue_file = r"D:\DGH\Data\Videos\catalogue.csv"
rootdir = r"D:\Project\ASOID-Models\Apr-29-2026\videos"

# Create destination folders
os.makedirs(os.path.join(rootdir, "VG"), exist_ok=True)
os.makedirs(os.path.join(rootdir, "SE"), exist_ok=True)

# ─────────────────────────────────────────────────────────────
# 1. Load and parse the catalogue CSV
# ─────────────────────────────────────────────────────────────
# CSV format: "20250913 Marathon,3,D,SE" → [date_type, individual, letter, quality]
catalogue = pd.read_csv(
    catalogue_file, 
    header=None, 
    names=['date_type', 'individual', 'letter', 'quality'],
    
    skipinitialspace=True  # handles spaces after commas
)

# Extract pure date (YYYYMMDD) from "20250913 Marathon"
catalogue['date'] = catalogue['date_type'].str.extract(r'(\d{8})')[0]
catalogue['individual'] = catalogue['individual'].astype(int)

# Build lookup: (MMDD, individual) → quality rating
# We use last 4 digits of date (MMDD) to match Processing ID format
lookup = {}
for _, row in catalogue.iterrows():
    mmdd = row['date'][-4:]  # e.g., "0324" from "20260324"
    key = (mmdd, row['individual'])
    lookup[key] = row['quality'].strip().upper()  # ensure "SE"/"VG"

print(f"✓ Loaded {len(lookup)} catalogue entries")

# ─────────────────────────────────────────────────────────────
# 2. Process .mat files in rootdir
# ─────────────────────────────────────────────────────────────
# Expected filename pattern: MMDDF{individual}day{N}.mat
# e.g., "0324F2day1.mat" → date=0324, individual=2
pattern = re.compile(r'^(\d{4})F(\d+)day\d+\.mat$')

moved_count = 0
skipped_count = 0

for filename in os.listdir(rootdir):
    if not filename.endswith('.mat'):
        continue
    
    match = pattern.match(filename)
    if not match:
        print(f"⚠ Skipping unrecognized filename: {filename}")
        skipped_count += 1
        continue
    
    mmdd = match.group(1)          # e.g., "0324"
    individual = int(match.group(2))  # e.g., 2
    lookup_key = (mmdd, individual)
    
    quality = lookup.get(lookup_key)
    if not quality or quality not in ['SE', 'VG']:
        print(f"⚠ No valid catalogue entry for {filename} (key: {lookup_key})")
        skipped_count += 1
        continue
    
    # Move file to appropriate folder
    src = os.path.join(rootdir, filename)
    dst_dir = os.path.join(rootdir, quality)
    dst = os.path.join(dst_dir, filename)
    
    shutil.move(src, dst)
    print(f"✓ Moved {filename} → {quality}/")
    moved_count += 1

# ─────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────
print(f"\n📊 Done! Moved: {moved_count} files | Skipped: {skipped_count} files")
print(f"📁 Files now sorted in:\n   {os.path.join(rootdir, 'SE')}\n   {os.path.join(rootdir, 'VG')}")