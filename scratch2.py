import re

with open('templates/releases/global_release_list.html', 'r') as f:
    html = f.read()

replacement = """
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
                                    <a href="{% url 'tasks:release_detail' release.pk %}" class="asset-item" style="border-style: dashed;">
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

old_pattern = r'<div class="release-timeline">.*?</div>\s*</div>\s*<!-- end inner div for timeline -->'
# wait, the structure ends with {% endfor %} inside the timeline.
import re
html = re.sub(r'<div class="release-timeline">.*?</div>\s*</div>\s*{% endfor %}', replacement.strip() + '\n            </div>\n            {% endfor %}', html, flags=re.DOTALL)

with open('templates/releases/global_release_list.html', 'w') as f:
    f.write(html)
