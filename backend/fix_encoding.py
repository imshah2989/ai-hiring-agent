import os

files_to_fix = ["app.py", "server.py", "README.md"]
for filename in files_to_fix:
    if os.path.exists(filename):
        print(f"Fixing {filename}...")
        # Read as any encoding (likely utf-16le or with BOM)
        try:
            with open(filename, 'rb') as f:
                content = f.read()
            
            # Remove UTF-16 BOM or just decode correctly
            if content.startswith(b'\xff\xfe') or content.startswith(b'\xfe\xff'):
                text = content.decode('utf-16')
            else:
                text = content.decode('utf-8', errors='ignore')
            
            # Write back as clean UTF-8
            with open(filename, 'w', encoding='utf-8', newline='\n') as f:
                f.write(text)
            print(f"✅ {filename} converted to UTF-8.")
        except Exception as e:
            print(f"❌ Failed to fix {filename}: {e}")
