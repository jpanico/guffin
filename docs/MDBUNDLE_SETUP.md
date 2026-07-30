# Setting Up .mdbundle Auto-Open with Typora

This guide explains how to configure macOS to automatically open `.mdbundle` folders in Typora when double-clicked.

## Overview

A `.mdbundle` folder contains:
- A markdown file (e.g., `notes.md`)
- Associated images and assets

When you double-click `notes.md.mdbundle/`, macOS should open `notes.md` in Typora.

## Setup Instructions

### Method 1: Automator Application (Recommended)

1. **Open Automator** (Applications > Automator)

2. **Create New Application**
   - Choose "Application" as the document type
   - Click "Choose"

3. **Add Run Shell Script Action**
   - In the left sidebar, find "Run Shell Script" under "Utilities"
   - Drag it to the workflow area
   - Set "Pass input" to "as arguments"
   - Paste this script:

   ```bash
   #!/bin/bash

   # Get the .mdbundle folder path from the argument
   bundle_path="$1"

   # Get the folder name without the path
   bundle_name=$(basename "$bundle_path")

   # Remove .mdbundle extension to get the .md filename
   md_filename="${bundle_name%.mdbundle}"

   # Construct full path to the .md file
   md_file="$bundle_path/$md_filename"

   # Open in Typora
   open -a "Typora" "$md_file"
   ```

4. **Save the Application**
   - File > Save
   - Name: `Open MDBundle`
   - Location: `/Applications/` or `~/Applications/`
   - Format: Application
   - Click Save

5. **Associate .mdbundle with the Application**
   - Find any `.mdbundle` folder in Finder
   - Right-click > Get Info (⌘I)
   - Under "Open with:", select "Other..."
   - Navigate to your "Open MDBundle.app"
   - Check "Always Open With"
   - Click "Add"
   - Click "Change All..." to apply to all `.mdbundle` folders

### Method 2: Quick Action (Alternative)

1. **Open Automator**

2. **Create New Quick Action**
   - Choose "Quick Action" as the document type

3. **Configure Workflow Settings**
   - "Workflow receives current": folders
   - in: Finder

4. **Add Run Shell Script** (same script as above)

5. **Save**
   - Name: "Open in Typora"
   - Location will be saved to `~/Library/Services/`

6. **Use it**
   - Right-click any `.mdbundle` folder
   - Services > Open in Typora

### Method 3: Custom .app Bundle (Advanced)

For a more integrated solution, create a custom application bundle:

1. **Create Application Structure**
   ```bash
   mkdir -p ~/Applications/OpenMDBundle.app/Contents/MacOS
   mkdir -p ~/Applications/OpenMDBundle.app/Contents/Resources
   ```

2. **Create Info.plist**
   ```bash
   cat > ~/Applications/OpenMDBundle.app/Contents/Info.plist << 'EOF'
   <?xml version="1.0" encoding="UTF-8"?>
   <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
   <plist version="1.0">
   <dict>
       <key>CFBundleDevelopmentRegion</key>
       <string>en</string>
       <key>CFBundleExecutable</key>
       <string>open-mdbundle</string>
       <key>CFBundleIdentifier</key>
       <string>com.local.openmdbundle</string>
       <key>CFBundleInfoDictionaryVersion</key>
       <string>6.0</string>
       <key>CFBundleName</key>
       <string>OpenMDBundle</string>
       <key>CFBundlePackageType</key>
       <string>APPL</string>
       <key>CFBundleShortVersionString</key>
       <string>1.0</string>
       <key>CFBundleVersion</key>
       <string>1</string>
       <key>CFBundleDocumentTypes</key>
       <array>
           <dict>
               <key>CFBundleTypeExtensions</key>
               <array>
                   <string>mdbundle</string>
               </array>
               <key>CFBundleTypeName</key>
               <string>Markdown Bundle</string>
               <key>CFBundleTypeRole</key>
               <string>Viewer</string>
               <key>LSHandlerRank</key>
               <string>Owner</string>
           </dict>
       </array>
   </dict>
   </plist>
   EOF
   ```

3. **Create Executable Script**
   ```bash
   cat > ~/Applications/OpenMDBundle.app/Contents/MacOS/open-mdbundle << 'EOF'
   #!/bin/bash

   # Get the .mdbundle folder path
   bundle_path="$1"

   # Get the folder name without the path
   bundle_name=$(basename "$bundle_path")

   # Remove .mdbundle extension to get the .md filename
   md_filename="${bundle_name%.mdbundle}"

   # Construct full path to the .md file
   md_file="$bundle_path/$md_filename"

   # Open in Typora
   open -a "Typora" "$md_file"
   EOF
   ```

4. **Make Executable**
   ```bash
   chmod +x ~/Applications/OpenMDBundle.app/Contents/MacOS/open-mdbundle
   ```

5. **Register with Launch Services**
   ```bash
   /System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -f ~/Applications/OpenMDBundle.app
   ```

6. **Associate .mdbundle files** (same as Method 1, step 5)

## Troubleshooting

### "Open with" doesn't show OpenMDBundle
This happens if the `.mdbundle` folder was created before setting up the handler.

**Solution 1: Refresh the folder**
```bash
mdimport ~/path/to/your.mdbundle
```

**Solution 2: Set handler using duti (if installed)**
```bash
duti -s com.local.openmdbundle com.local.markdown-bundle all
```

### Verify folder is recognized correctly
```bash
mdls ~/path/to/your.mdbundle | grep kMDItemContentType
```

Should show: `kMDItemContentType = "com.local.markdown-bundle"`

If it shows `"public.folder"`, run `mdimport` on the folder.

### "The application cannot be opened" error
- Make sure the script is executable: `chmod +x <script>`
- Check the Typora path: `open -a "Typora"` should work in Terminal

### Changes not taking effect
- Log out and log back in
- Or run: `killall Finder`

### .mdbundle still opens in wrong app
- Right-click the folder > Get Info
- Under "Open with:", select OpenMDBundle
- Click "Change All..."

### Check if UTI is registered
```bash
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -dump | grep -A 10 "mdbundle"
```

## Testing

1. Create a test bundle:
   ```bash
   mkdir test.md.mdbundle
   echo "# Test" > test.md.mdbundle/test.md
   ```

2. Double-click `test.md.mdbundle` in Finder

3. Typora should open with `test.md`

## Notes

- The script assumes the `.md` file has the same base name as the `.mdbundle` folder
- Example: `notes.md.mdbundle/` contains `notes.md`
- If Typora is in a non-standard location, update the script with the full path
