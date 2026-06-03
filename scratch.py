import re

with open('templates/releases/release_list.html', 'r') as f:
    release_css = re.search(r'<style>(.*?)</style>', f.read(), re.DOTALL).group(1)

with open('templates/releases/global_release_list.html', 'r') as f:
    global_html = f.read()

# Replace the style
new_style = """<style>
    .releases-layout {
        display: grid;
        grid-template-columns: 280px 1fr;
        gap: 30px;
        align-items: start;
        margin-top: 20px;
    }
    .releases-sidebar {
        position: sticky;
        top: 100px;
        background: var(--bg-card);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 20px;
        max-height: calc(100vh - 140px);
        display: flex;
        flex-direction: column;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.05);
    }
    .search-box {
        position: relative;
        margin-bottom: 20px;
    }
    .search-box input {
        width: 100%;
        padding: 10px 15px 10px 40px;
        border-radius: 10px;
        border: 1px solid var(--border);
        background: var(--bg-secondary);
        color: var(--text-primary);
        font-size: 14px;
        outline: none;
        transition: border-color 0.2s;
    }
    .search-box input:focus { border-color: var(--accent); }
    .search-box i { position: absolute; left: 15px; top: 50%; transform: translateY(-50%); color: var(--text-muted); }
    
    .project-nav { overflow-y: auto; flex: 1; margin: 0 -10px; padding: 0 10px; }
    .project-nav-item {
        display: block; padding: 10px 12px; border-radius: 8px; text-decoration: none;
        color: var(--text-secondary); font-size: 14px; font-weight: 500; margin-bottom: 4px;
        transition: all 0.2s; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
    }
    .project-nav-item:hover { background: rgba(var(--accent-rgb), 0.05); color: var(--accent); }
    .project-nav-item.active { background: var(--accent); color: white; }

    @media (max-width: 992px) {
        .releases-layout { grid-template-columns: 1fr; }
        .releases-sidebar { position: relative; top: 0; max-height: none; }
    }
""" + release_css + "</style>"

global_html = re.sub(r'<style>.*?</style>', new_style, global_html, flags=re.DOTALL)

with open('templates/releases/global_release_list.html', 'w') as f:
    f.write(global_html)
