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

replacement_html = """
                <div class="timeline-layout">
                    {% for release in group.releases %}
                    <div class="release-item {% if forloop.first %}latest{% endif %}">
                        <div class="release-dot"></div>
                        <div class="release-main">
                            <div class="release-header">
                                <div class="release-title-area">
                                    <h2>
                                        <a href="{% url 'tasks:release_detail' release.pk %}">{{ release.name }}</a>
                                        {% if forloop.first %}
                                            <span class="badge badge-latest">Latest</span>
                                        {% endif %}
                                        {% if release.is_draft %}
                                            <span class="badge badge-draft">Draft</span>
                                        {% endif %}
                                        {% if release.is_prerelease %}
                                            <span class="badge badge-pre">Pre-release</span>
                                        {% endif %}
                                    </h2>
                                    <div class="tag-info">
                                        <span><i class="fas fa-tag"></i> {{ release.tag_name|default:release.version }}</span>
                                        <span>•</span>
                                        <span><i class="far fa-calendar-alt"></i> {{ release.release_date|date:"M d, Y" }}</span>
                                        <span>•</span>
                                        <span><i class="fas fa-sliders-h"></i> {{ release.get_release_type_display }}</span>
                                    </div>
                                </div>
                                <div class="release-actions">
                                    <a href="{% url 'tasks:release_detail' release.pk %}" class="btn btn-secondary btn-sm" title="View Details">Details <i class="fas fa-arrow-right"></i></a>
                                </div>
                            </div>

                            <div class="release-body">
                                <div class="markdown-content">{{ release.description|truncatewords:40|linebreaks }}</div>
                            </div>

                            {% if release.direct_files.exists or release.module_versions.exists %}
                            <div class="assets-section">
                                <div class="assets-title"><i class="fas fa-paperclip"></i> Immutable Assets</div>
                                <div class="asset-list">
                                    {% for file in release.direct_files.all|slice:":2" %}
                                    <a href="{% url 'files:file_download' file.pk %}" class="asset-item" download>
                                        <i class="fas {{ file.icon_class }}" style="color: {{ file.icon_color }};"></i>
                                        <div class="asset-meta-info">
                                            <div class="asset-name">{{ file.original_name }}</div>
                                            <div class="asset-size">{{ file.file_size_display }}</div>
                                        </div>
                                        <i class="fas fa-download" style="opacity: 0.5;"></i>
                                    </a>
                                    {% endfor %}
                                    {% if release.direct_files.count > 2 or release.module_versions.count > 0 %}
                                    <a href="{% url 'tasks:release_detail' release.pk %}" class="asset-item" style="border-style: dashed; text-decoration: none;">
                                        <i class="fas fa-ellipsis-h" style="color: var(--text-muted);"></i>
                                        <div class="asset-meta-info">
                                            <div class="asset-name" style="font-weight: 700;">More assets</div>
                                            <div class="asset-size">View release to see all assets</div>
                                        </div>
                                        <i class="fas fa-arrow-right" style="opacity: 0.5;"></i>
                                    </a>
                                    {% endif %}
                                </div>
                            </div>
                            {% endif %}
                            
                            <div class="release-footer">
                                <div class="released-by">
                                    <img src="https://ui-avatars.com/api/?name={{ release.author.username }}&background=random&color=fff" alt="{{ release.author.display_name }}">
                                    <span>Drafted by <strong>{{ release.author.display_name|default:release.author.username }}</strong></span>
                                </div>
                                <div style="font-size: 11px; color: var(--text-muted);">
                                    Release ID: #{{ release.pk }}
                                </div>
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                </div>
"""

global_html = re.sub(r'<div class="release-timeline">.*?</div>\s*</div>\s*{% endfor %}', replacement_html.strip() + '\n            </div>\n            {% endfor %}', global_html, flags=re.DOTALL)

with open('templates/releases/global_release_list.html', 'w') as f:
    f.write(global_html)
