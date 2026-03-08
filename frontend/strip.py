import sys

def process_index():
    with open('index.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # Change button to link
    btn_str = '<button class="btn btn-primary hero-btn" id="startStaticBtn">ENTER PIPELINE ↓</button>'
    lnk_str = '<a href="pipeline.html" class="btn btn-primary hero-btn" id="startStaticBtn">ENTER PIPELINE ↓</a>'
    content = content.replace(btn_str, lnk_str)

    # Cut out the pipeline
    nav_idx = content.find('<!-- ── NAV ── -->')
    footer_idx = content.find('<!-- ── FOOTER ── -->')
    if nav_idx != -1 and footer_idx != -1:
        content = content[:nav_idx] + content[footer_idx:]

    # Remove app.js
    content = content.replace('<script src="app.js"></script>', '')

    with open('index.html', 'w', encoding='utf-8') as f:
        f.write(content)

def process_pipeline():
    with open('pipeline.html', 'r', encoding='utf-8') as f:
        content = f.read()

    # Cut out the hero
    hero_idx = content.find('<!-- ── HERO STATIC ── -->')
    nav_idx = content.find('<!-- ── NAV ── -->')
    if hero_idx != -1 and nav_idx != -1:
        content = content[:hero_idx] + content[nav_idx:]

    # Update logo link
    content = content.replace('<a class="nav-logo" href="#">Co-Pilot</a>', '<a class="nav-logo" href="index.html">Co-Pilot</a>')

    with open('pipeline.html', 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    process_index()
    process_pipeline()
    print("HTML processing complete!")
