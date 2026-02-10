/* PaperJam Web — Main Application */

const App = {
    user: null,
    currentView: 'library',
    viewStack: [],
    playlists: [],

    async init() {
        try {
            this.user = await API.me();
        } catch {
            window.location.href = '/login';
            return;
        }

        document.getElementById('user-menu-btn').textContent = this.user.display_name || this.user.username;

        Player.init();
        this._bindEvents();
        this._applyTheme();
        this.navigate('library');

        // Register service worker
        if ('serviceWorker' in navigator) {
            navigator.serviceWorker.register('/static/sw.js').catch(() => {});
        }
    },

    _bindEvents() {
        // Nav buttons
        document.getElementById('main-nav').addEventListener('click', (e) => {
            const btn = e.target.closest('button[data-view]');
            if (!btn) return;
            this.viewStack = [];
            this.navigate(btn.dataset.view);
        });

        // Search toggle
        const searchBar = document.getElementById('search-bar');
        const searchInput = document.getElementById('search-input');
        const searchToggle = document.getElementById('search-toggle');
        let searchTimeout;

        const closeSearch = () => {
            searchBar.hidden = true;
            searchToggle.classList.remove('active');
            searchInput.value = '';
            if (this.currentView === 'search') this.navigate('library');
        };

        searchToggle.addEventListener('click', () => {
            if (searchBar.hidden) {
                searchBar.hidden = false;
                searchToggle.classList.add('active');
                searchInput.focus();
            } else {
                closeSearch();
            }
        });

        document.getElementById('search-close').addEventListener('click', () => closeSearch());

        searchInput.addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(() => {
                const q = searchInput.value.trim();
                if (q.length >= 2) this.showSearch(q);
                else if (this.currentView === 'search') this.navigate('library');
            }, 300);
        });

        searchInput.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') closeSearch();
        });

        // Player controls
        document.getElementById('btn-play').addEventListener('click', () => Player.toggle());
        document.getElementById('btn-prev').addEventListener('click', () => Player.prev());
        document.getElementById('btn-next').addEventListener('click', () => Player.next());
        document.getElementById('btn-shuffle').addEventListener('click', () => Player.toggleShuffle());
        document.getElementById('btn-loop').addEventListener('click', () => Player.cycleLoop());
        document.getElementById('btn-queue').addEventListener('click', () => {
            this.viewStack.push(this.currentView);
            this.navigate('queue');
        });
        document.getElementById('btn-fav').addEventListener('click', async () => {
            if (!Player.currentTrack) return;
            const r = await API.toggleFavorite('track', Player.currentTrack.path);
            document.getElementById('btn-fav').classList.toggle('active', r.favorited);
            this.toast(r.favorited ? 'Added to favorites' : 'Removed from favorites');
        });

        // Progress bar seeking
        document.getElementById('progress-bar').addEventListener('click', (e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const frac = (e.clientX - rect.left) / rect.width;
            Player.seekTo(Math.max(0, Math.min(1, frac)));
        });

        // Volume
        document.getElementById('volume-slider').addEventListener('input', (e) => {
            Player.setVolume(parseInt(e.target.value));
        });

        // User menu
        document.getElementById('user-menu-btn').addEventListener('click', () => {
            this._showUserMenu();
        });

        // Now playing click
        document.getElementById('player-info-click').addEventListener('click', () => {
            if (Player.currentTrack) {
                this.viewStack.push(this.currentView);
                this.navigate('now-playing');
            }
        });
        document.getElementById('player-cover-click').addEventListener('click', () => {
            if (Player.currentTrack) {
                this.viewStack.push(this.currentView);
                this.navigate('now-playing');
            }
        });

        // Close context menu on click outside
        document.addEventListener('click', () => {
            document.getElementById('context-menu').hidden = true;
        });

        // Modal close on overlay click
        document.getElementById('modal-overlay').addEventListener('click', (e) => {
            if (e.target === e.currentTarget) this.closeModal();
        });
    },

    // --- Navigation ---

    navigate(view, data) {
        this.currentView = view;
        this._updateNav(view);

        const content = document.getElementById('content');
        content.innerHTML = '<div class="loading">Loading</div>';

        switch (view) {
            case 'library': this._renderLibrary(content); break;
            case 'artists': this._renderArtists(content); break;
            case 'artist': this._renderArtist(content, data); break;
            case 'albums': this._renderAlbums(content); break;
            case 'album': this._renderAlbum(content, data); break;
            case 'playlists': this._renderPlaylists(content); break;
            case 'playlist': this._renderPlaylist(content, data); break;
            case 'recents': this._renderRecents(content); break;
            case 'favorites': this._renderFavorites(content); break;
            case 'settings': this._renderSettings(content); break;
            case 'admin': this._renderAdmin(content); break;
            case 'search': this.showSearch(data, true); break;
            case 'queue': this._renderQueue(content); break;
            case 'now-playing': this._renderNowPlaying(content); break;
        }
    },

    goBack() {
        if (this.viewStack.length > 0) {
            this.navigate(this.viewStack.pop());
        } else {
            this.navigate('library');
        }
    },

    _updateNav(view) {
        const btns = document.querySelectorAll('#main-nav button');
        btns.forEach(b => b.classList.toggle('active', b.dataset.view === view));
        document.getElementById('breadcrumb').hidden = true;
    },

    _setBreadcrumb(...items) {
        const bc = document.getElementById('breadcrumb');
        bc.hidden = false;
        bc.innerHTML = '';
        items.forEach((item, i) => {
            if (i > 0) {
                const sep = document.createElement('span');
                sep.className = 'sep';
                sep.textContent = '/';
                bc.appendChild(sep);
            }
            if (i === items.length - 1) {
                const span = document.createElement('span');
                span.className = 'current';
                span.textContent = item.label;
                bc.appendChild(span);
            } else {
                const span = document.createElement('span');
                span.textContent = item.label;
                span.addEventListener('click', item.action);
                bc.appendChild(span);
            }
        });
    },

    // --- Views ---

    async _renderLibrary(el) {
        try {
            const [stats, recents] = await Promise.all([
                API.libraryStats(),
                API.recents().catch(() => []),
            ]);
            el.innerHTML = '';

            const header = document.createElement('div');
            header.className = 'section-header';
            header.textContent = 'Library';
            el.appendChild(header);

            // Stats overview
            const statsDiv = document.createElement('div');
            statsDiv.className = 'settings-item';
            statsDiv.innerHTML = `<span class="settings-label">${stats.artists} artists · ${stats.albums} albums · ${stats.tracks} tracks</span>
                <span class="settings-value">${stats.total_duration}</span>`;
            el.appendChild(statsDiv);

            if (stats.scanning) {
                const scanDiv = document.createElement('div');
                scanDiv.className = 'settings-item';
                scanDiv.innerHTML = `<span class="settings-label">Scanning...</span>
                    <span class="settings-value">${stats.scan_progress} / ${stats.scan_total}</span>`;
                el.appendChild(scanDiv);
            }

            // All Tracks shortcut
            const allTracksDiv = this._createListItem(this._icon('tracks'), 'All Tracks', `${stats.tracks} tracks`, null, () => this._renderAllTracks(el));
            el.appendChild(allTracksDiv);

            // Recent plays preview
            if (recents.length > 0) {
                const recentHeader = document.createElement('div');
                recentHeader.className = 'section-header';
                recentHeader.textContent = 'Recently Played';
                el.appendChild(recentHeader);

                recents.slice(0, 5).forEach(r => {
                    const filename = r.track_path.split('/').pop();
                    const div = this._createListItem(this._icon('recent'), filename, '', null, () => {
                        const track = { path: r.track_path, title: filename, artist: '', album: '' };
                        Player.play(track, [track], 0);
                    });
                    el.appendChild(div);
                });
            }
        } catch (e) {
            el.innerHTML = `<div class="empty-state">Error loading library: ${e.message}</div>`;
        }
    },

    async _renderAllTracks(el) {
        el.innerHTML = '<div class="loading">Loading tracks</div>';
        try {
            const tracks = await API.tracks();
            el.innerHTML = '';
            this._setBreadcrumb(
                { label: 'Library', action: () => this.navigate('library') },
                { label: 'All Tracks' }
            );

            if (tracks.length === 0) {
                el.innerHTML = '<div class="empty-state">No tracks found</div>';
                return;
            }

            const actionsDiv = document.createElement('div');
            actionsDiv.className = 'album-actions';
            actionsDiv.style.padding = 'var(--pad)';
            actionsDiv.style.borderBottom = 'var(--cell)';

            const playAllBtn = document.createElement('button');
            playAllBtn.className = 'btn-small';
            playAllBtn.textContent = 'Play All';
            playAllBtn.addEventListener('click', () => {
                Player.play(tracks[0], tracks, 0);
            });
            actionsDiv.appendChild(playAllBtn);

            const shuffleBtn = document.createElement('button');
            shuffleBtn.className = 'btn-small';
            shuffleBtn.textContent = 'Shuffle All';
            shuffleBtn.addEventListener('click', () => {
                const shuffled = [...tracks].sort(() => Math.random() - 0.5);
                Player.play(shuffled[0], shuffled, 0);
            });
            actionsDiv.appendChild(shuffleBtn);

            el.appendChild(actionsDiv);

            tracks.forEach((t, i) => {
                const div = this._createTrackItem(t, () => {
                    Player.play(t, tracks, i);
                });
                el.appendChild(div);
            });
        } catch (e) {
            el.innerHTML = `<div class="empty-state">Error: ${e.message}</div>`;
        }
    },

    async _renderArtists(el) {
        try {
            const artists = await API.artists();
            el.innerHTML = '';

            const header = document.createElement('div');
            header.className = 'section-header';
            header.textContent = `Artists (${artists.length})`;
            el.appendChild(header);

            artists.forEach(a => {
                const div = this._createListItem(
                    this._icon('artist'), a.name,
                    `${a.album_count} albums · ${a.track_count} tracks`,
                    null,
                    () => {
                        this.viewStack.push('artists');
                        this.navigate('artist', a.name);
                    }
                );
                el.appendChild(div);
            });
        } catch (e) {
            el.innerHTML = `<div class="empty-state">Error: ${e.message}</div>`;
        }
    },

    async _renderArtist(el, name) {
        try {
            const artist = await API.artist(name);
            el.innerHTML = '';
            this._setBreadcrumb(
                { label: 'Artists', action: () => this.navigate('artists') },
                { label: artist.name }
            );

            const header = document.createElement('div');
            header.className = 'section-header';
            header.textContent = artist.name;
            el.appendChild(header);

            artist.albums.forEach(album => {
                const albumDiv = this._createListItem(
                    this._icon('album'), album.name,
                    `${album.year || ''} · ${album.track_count} tracks`,
                    null,
                    () => {
                        this.viewStack.push('artist');
                        this.navigate('album', album.name);
                    }
                );
                el.appendChild(albumDiv);
            });
        } catch (e) {
            el.innerHTML = `<div class="empty-state">Error: ${e.message}</div>`;
        }
    },

    async _renderAlbums(el) {
        try {
            const albums = await API.albums();
            el.innerHTML = '';

            const header = document.createElement('div');
            header.className = 'section-header';
            header.textContent = `Albums (${albums.length})`;
            el.appendChild(header);

            albums.forEach(a => {
                const div = this._createListItem(
                    null, a.name,
                    `${a.artist} · ${a.track_count} tracks`,
                    a.path || null,
                    () => {
                        this.viewStack.push('albums');
                        this.navigate('album', a.name);
                    }
                );
                el.appendChild(div);
            });
        } catch (e) {
            el.innerHTML = `<div class="empty-state">Error: ${e.message}</div>`;
        }
    },

    async _renderAlbum(el, name) {
        try {
            const album = await API.album(name);
            el.innerHTML = '';
            this._setBreadcrumb(
                { label: 'Albums', action: () => this.navigate('albums') },
                { label: album.name }
            );

            // Album header
            const headerDiv = document.createElement('div');
            headerDiv.className = 'album-header';

            const coverDiv = document.createElement('div');
            coverDiv.className = 'album-cover';
            if (album.tracks.length > 0) {
                const img = document.createElement('img');
                img.src = API.coverUrl(album.tracks[0].path, 'large');
                img.onerror = () => { coverDiv.innerHTML = this._icon('tracks', 32); };
                coverDiv.appendChild(img);
            }
            headerDiv.appendChild(coverDiv);

            const infoDiv = document.createElement('div');
            infoDiv.className = 'album-info';
            infoDiv.innerHTML = `
                <div class="album-title">${this._esc(album.name)}</div>
                <div class="album-artist">${this._esc(album.artist)}</div>
                <div class="album-meta">${album.year || ''} · ${album.track_count} tracks · ${album.duration}</div>
                <div class="album-actions">
                    <button class="btn-small" id="album-play-all">${this._icon('gt')} Play</button>
                    <button class="btn-small" id="album-shuffle">Shuffle</button>
                    <button class="btn-small" id="album-fav">${this._icon('heart')} Fav</button>
                </div>`;
            headerDiv.appendChild(infoDiv);
            el.appendChild(headerDiv);

            // Play/shuffle handlers
            el.querySelector('#album-play-all').addEventListener('click', () => {
                Player.play(album.tracks[0], album.tracks, 0);
            });
            el.querySelector('#album-shuffle').addEventListener('click', () => {
                const shuffled = [...album.tracks].sort(() => Math.random() - 0.5);
                Player.play(shuffled[0], shuffled, 0);
            });

            // Favorite button
            API.checkFavorite('album', album.name).then(r => {
                const btn = el.querySelector('#album-fav');
                btn.innerHTML = `${this._icon('heart')} ${r.favorited ? 'Fav\'d' : 'Fav'}`;
                btn.classList.toggle('active', r.favorited);
            }).catch(() => {});

            el.querySelector('#album-fav').addEventListener('click', async () => {
                const r = await API.toggleFavorite('album', album.name);
                const btn = el.querySelector('#album-fav');
                btn.innerHTML = `${this._icon('heart')} ${r.favorited ? 'Fav\'d' : 'Fav'}`;
                btn.classList.toggle('active', r.favorited);
                this.toast(r.favorited ? 'Album added to favorites' : 'Album removed from favorites');
            });

            // Track list
            album.tracks.forEach((t, i) => {
                const div = this._createTrackItem(t, () => {
                    Player.play(t, album.tracks, i);
                }, true);
                el.appendChild(div);
            });
        } catch (e) {
            el.innerHTML = `<div class="empty-state">Error: ${e.message}</div>`;
        }
    },

    async _renderPlaylists(el) {
        try {
            const playlists = await API.playlists();
            this.playlists = playlists;
            el.innerHTML = '';

            const header = document.createElement('div');
            header.className = 'section-header';
            header.textContent = 'Playlists';
            el.appendChild(header);

            // New playlist button
            const newBtn = this._createListItem(this._icon('plus'), 'New Playlist', '', null, () => {
                this._showCreatePlaylistModal();
            });
            el.appendChild(newBtn);

            if (playlists.length === 0) {
                el.innerHTML += '<div class="empty-state">No playlists yet</div>';
                return;
            }

            playlists.forEach(p => {
                const div = this._createListItem(
                    this._icon('playlist'), p.name,
                    `${p.track_count} tracks`,
                    null,
                    () => {
                        this.viewStack.push('playlists');
                        this.navigate('playlist', p.id);
                    }
                );
                // Context menu for playlist
                div.addEventListener('contextmenu', (e) => {
                    e.preventDefault();
                    this._showContextMenu(e, [
                        { label: 'Rename', action: () => this._showRenamePlaylistModal(p) },
                        { label: 'Delete', action: async () => {
                            await API.deletePlaylist(p.id);
                            this.toast('Playlist deleted');
                            this.navigate('playlists');
                        }},
                    ]);
                });
                el.appendChild(div);
            });
        } catch (e) {
            el.innerHTML = `<div class="empty-state">Error: ${e.message}</div>`;
        }
    },

    async _renderPlaylist(el, id) {
        try {
            const [playlist, allPlaylists] = await Promise.all([
                API.playlist(id),
                API.playlists(),
            ]);
            const meta = allPlaylists.find(p => p.id === id);
            el.innerHTML = '';

            this._setBreadcrumb(
                { label: 'Playlists', action: () => this.navigate('playlists') },
                { label: meta?.name || `Playlist ${id}` }
            );

            const header = document.createElement('div');
            header.className = 'section-header';
            header.textContent = meta?.name || `Playlist ${id}`;
            el.appendChild(header);

            if (playlist.tracks.length === 0) {
                el.innerHTML += '<div class="empty-state">Empty playlist</div>';
                return;
            }

            // TODO: resolve track metadata from paths. For now show paths.
            playlist.tracks.forEach((pt, i) => {
                const div = this._createListItem(
                    String(i + 1), pt.track_path.split('/').pop(),
                    pt.track_path, null,
                    () => {
                        // Build tracks array from paths
                        const tracks = playlist.tracks.map(t => ({
                            path: t.track_path,
                            title: t.track_path.split('/').pop(),
                            artist: '',
                            album: '',
                        }));
                        Player.play(tracks[i], tracks, i);
                    }
                );
                el.appendChild(div);
            });
        } catch (e) {
            el.innerHTML = `<div class="empty-state">Error: ${e.message}</div>`;
        }
    },

    async _renderRecents(el) {
        try {
            const recents = await API.recents();
            el.innerHTML = '';

            const header = document.createElement('div');
            header.className = 'section-header';
            header.textContent = 'Recently Played';
            el.appendChild(header);

            if (recents.length === 0) {
                el.innerHTML += '<div class="empty-state">No recent plays</div>';
                return;
            }

            recents.forEach(r => {
                const filename = r.track_path.split('/').pop();
                const div = this._createListItem(
                    this._icon('recent'), filename, r.track_path, null,
                    () => {
                        const track = { path: r.track_path, title: filename, artist: '', album: '' };
                        Player.play(track, [track], 0);
                    }
                );
                el.appendChild(div);
            });
        } catch (e) {
            el.innerHTML = `<div class="empty-state">Error: ${e.message}</div>`;
        }
    },

    async _renderFavorites(el) {
        try {
            const [tracks, albums, artists] = await Promise.all([
                API.favorites('track'),
                API.favorites('album'),
                API.favorites('artist'),
            ]);
            el.innerHTML = '';

            // Artists
            if (artists.length > 0) {
                const h = document.createElement('div');
                h.className = 'section-header';
                h.textContent = `Favorite Artists (${artists.length})`;
                el.appendChild(h);
                artists.forEach(a => {
                    const div = this._createListItem(this._icon('artist'), a.item_key, '', null, () => {
                        this.viewStack.push('favorites');
                        this.navigate('artist', a.item_key);
                    });
                    el.appendChild(div);
                });
            }

            // Albums
            if (albums.length > 0) {
                const h = document.createElement('div');
                h.className = 'section-header';
                h.textContent = `Favorite Albums (${albums.length})`;
                el.appendChild(h);
                albums.forEach(a => {
                    const div = this._createListItem(this._icon('album'), a.item_key, '', null, () => {
                        this.viewStack.push('favorites');
                        this.navigate('album', a.item_key);
                    });
                    el.appendChild(div);
                });
            }

            // Tracks
            if (tracks.length > 0) {
                const h = document.createElement('div');
                h.className = 'section-header';
                h.textContent = `Favorite Tracks (${tracks.length})`;
                el.appendChild(h);
                tracks.forEach(t => {
                    const filename = t.item_key.split('/').pop();
                    const div = this._createListItem(this._icon('heart'), filename, '', null, () => {
                        const track = { path: t.item_key, title: filename, artist: '', album: '' };
                        Player.play(track, [track], 0);
                    });
                    el.appendChild(div);
                });
            }

            if (tracks.length === 0 && albums.length === 0 && artists.length === 0) {
                el.innerHTML = '<div class="empty-state">No favorites yet</div>';
            }
        } catch (e) {
            el.innerHTML = `<div class="empty-state">Error: ${e.message}</div>`;
        }
    },

    async _renderSettings(el) {
        try {
            const settings = await API.settings();
            el.innerHTML = '';

            const header = document.createElement('div');
            header.className = 'section-header';
            header.textContent = 'Settings';
            el.appendChild(header);

            // Streaming quality
            el.appendChild(this._createSettingSelect('Streaming Quality', 'streaming_quality', settings.streaming_quality, [
                { value: 'low', label: 'Low (128 kbps)' },
                { value: 'medium', label: 'Medium (192 kbps)' },
                { value: 'high', label: 'High (256 kbps)' },
                { value: 'extreme', label: 'Extreme (320 kbps)' },
                { value: 'original', label: 'Original (no transcoding)' },
            ], (val) => {
                Player.quality = val;
            }));

            // Theme
            el.appendChild(this._createSettingSelect('Theme', 'theme', settings.theme, [
                { value: 'dark', label: 'Dark' },
                { value: 'light', label: 'Light' },
            ], (val) => {
                document.documentElement.dataset.theme = val;
                const meta = document.querySelector('meta[name="theme-color"]');
                if (meta) meta.content = val === 'dark' ? '#121218' : '#e9e3d3';
            }));

            // Language
            el.appendChild(this._createSettingSelect('Language', 'locale', settings.locale, [
                { value: 'en', label: 'English' },
                { value: 'ko', label: '한국어' },
                { value: 'ja', label: '日本語' },
            ]));

            // Recents limit
            el.appendChild(this._createSettingSelect('Recents Limit', 'recents_limit', settings.recents_limit, [
                { value: '10', label: '10' },
                { value: '30', label: '30' },
                { value: '50', label: '50' },
                { value: '100', label: '100' },
            ]));

            // Account section
            const acctHeader = document.createElement('div');
            acctHeader.className = 'section-header';
            acctHeader.textContent = 'Account';
            el.appendChild(acctHeader);

            // Change password
            const pwItem = document.createElement('div');
            pwItem.className = 'list-item';
            pwItem.innerHTML = '<div class="item-info"><div class="item-title">Change Password</div></div>';
            pwItem.addEventListener('click', () => this._showChangePasswordModal());
            el.appendChild(pwItem);

            // Admin section
            if (this.user.is_admin) {
                const adminHeader = document.createElement('div');
                adminHeader.className = 'section-header';
                adminHeader.textContent = 'Admin';
                el.appendChild(adminHeader);

                const manageUsers = document.createElement('div');
                manageUsers.className = 'list-item';
                manageUsers.innerHTML = '<div class="item-info"><div class="item-title">Manage Users</div></div>';
                manageUsers.addEventListener('click', () => {
                    this.viewStack.push('settings');
                    this.navigate('admin');
                });
                el.appendChild(manageUsers);

                const rescanItem = document.createElement('div');
                rescanItem.className = 'list-item';
                rescanItem.innerHTML = '<div class="item-info"><div class="item-title">Rescan Library</div></div>';
                rescanItem.addEventListener('click', async () => {
                    await API.scanLibrary();
                    this.toast('Library scan started');
                });
                el.appendChild(rescanItem);
            }

            // About
            const aboutHeader = document.createElement('div');
            aboutHeader.className = 'section-header';
            aboutHeader.textContent = 'About';
            el.appendChild(aboutHeader);

            const stats = await API.libraryStats();
            const aboutDiv = document.createElement('div');
            aboutDiv.className = 'settings-item';
            aboutDiv.innerHTML = `<span class="settings-label">PaperJam Web</span>
                <span class="settings-value">v2.0</span>`;
            el.appendChild(aboutDiv);

            const statsDiv = document.createElement('div');
            statsDiv.className = 'settings-item';
            statsDiv.innerHTML = `<span class="settings-label">Library</span>
                <span class="settings-value">${stats.tracks} tracks · ${stats.artists} artists · ${stats.albums} albums</span>`;
            el.appendChild(statsDiv);

        } catch (e) {
            el.innerHTML = `<div class="empty-state">Error: ${e.message}</div>`;
        }
    },

    async _renderAdmin(el) {
        try {
            const users = await API.adminUsers();
            el.innerHTML = '';

            this._setBreadcrumb(
                { label: 'Settings', action: () => this.navigate('settings') },
                { label: 'Manage Users' }
            );

            const header = document.createElement('div');
            header.className = 'section-header';
            header.textContent = 'Users';
            el.appendChild(header);

            // Create user button
            const createBtn = this._createListItem(this._icon('plus'), 'Create User', '', null, () => {
                this._showCreateUserModal();
            });
            el.appendChild(createBtn);

            users.forEach(u => {
                const badge = u.is_admin ? 'Admin' : 'User';
                const div = this._createListItem(
                    null, u.display_name || u.username,
                    `@${u.username}`,
                    null,
                    () => {}
                );
                // Add badge
                const badgeEl = document.createElement('span');
                badgeEl.className = 'item-badge';
                badgeEl.textContent = badge;
                div.appendChild(badgeEl);

                // Context menu
                div.addEventListener('contextmenu', (e) => {
                    e.preventDefault();
                    const items = [
                        { label: 'Reset Password', action: () => this._showResetPasswordModal(u) },
                    ];
                    if (u.id !== this.user.user_id) {
                        items.push({ label: 'Delete User', action: async () => {
                            if (confirm(`Delete user ${u.username}?`)) {
                                await API.adminDeleteUser(u.id);
                                this.toast('User deleted');
                                this.navigate('admin');
                            }
                        }});
                    }
                    this._showContextMenu(e, items);
                });
                el.appendChild(div);
            });
        } catch (e) {
            el.innerHTML = `<div class="empty-state">Error: ${e.message}</div>`;
        }
    },

    _renderQueue(el) {
        el.innerHTML = '';

        const header = document.createElement('div');
        header.className = 'section-header';
        header.textContent = 'Queue';
        el.appendChild(header);

        const queue = Player.getQueue();
        if (queue.length === 0) {
            el.innerHTML += '<div class="empty-state">Queue is empty</div>';
            return;
        }

        queue.forEach((t, i) => {
            const div = document.createElement('div');
            div.className = `list-item queue-item${t.isCurrent ? ' current-track' : ''}`;
            div.innerHTML = `
                <span class="queue-num">${i + 1}</span>
                <div class="item-info">
                    <div class="item-title">${this._esc(t.title)}</div>
                    <div class="item-meta">${this._esc(t.artist)}</div>
                </div>
                <span class="item-duration">${t.duration_fmt || ''}</span>`;
            div.addEventListener('click', () => Player.playFromQueue(i));
            el.appendChild(div);
        });
    },

    _renderNowPlaying(el) {
        const t = Player.currentTrack;
        if (!t) {
            el.innerHTML = '<div class="empty-state">Nothing playing</div>';
            return;
        }

        this._setBreadcrumb(
            { label: 'Back', action: () => this.goBack() },
            { label: 'Now Playing' }
        );

        el.innerHTML = '';
        const np = document.createElement('div');
        np.className = 'now-playing-full';

        const coverDiv = document.createElement('div');
        coverDiv.className = 'np-cover';
        const coverImg = document.createElement('img');
        coverImg.src = API.coverUrl(t.path, 'large');
        coverImg.alt = '';
        coverImg.onerror = () => { coverDiv.innerHTML = this._icon('tracks', 32); };
        coverDiv.appendChild(coverImg);
        np.appendChild(coverDiv);

        const infoDiv = document.createElement('div');
        infoDiv.className = 'np-info';
        infoDiv.innerHTML = `
            <div class="np-title">${this._esc(t.title)}</div>
            <div class="np-artist">${this._esc(t.artist)}</div>
            ${t.album ? `<div class="np-album">${this._esc(t.album)}</div>` : ''}`;
        np.appendChild(infoDiv);
        el.appendChild(np);
    },

    async showSearch(query, skipSet) {
        if (!skipSet) {
            this.currentView = 'search';
            this._updateNav('search');
        }
        const el = document.getElementById('content');
        el.innerHTML = '<div class="loading">Searching</div>';

        try {
            const results = await API.search(query);
            el.innerHTML = '';

            if (results.artists.length > 0) {
                const h = document.createElement('div');
                h.className = 'section-header';
                h.textContent = `Artists (${results.artists.length})`;
                el.appendChild(h);
                results.artists.forEach(a => {
                    const div = this._createListItem(this._icon('artist'), a.name, `${a.track_count} tracks`, null, () => {
                        this.viewStack.push('search');
                        this.navigate('artist', a.name);
                    });
                    el.appendChild(div);
                });
            }

            if (results.albums.length > 0) {
                const h = document.createElement('div');
                h.className = 'section-header';
                h.textContent = `Albums (${results.albums.length})`;
                el.appendChild(h);
                results.albums.forEach(a => {
                    const div = this._createListItem(this._icon('album'), a.name, `${a.artist} · ${a.track_count} tracks`, null, () => {
                        this.viewStack.push('search');
                        this.navigate('album', a.name);
                    });
                    el.appendChild(div);
                });
            }

            if (results.tracks.length > 0) {
                const h = document.createElement('div');
                h.className = 'section-header';
                h.textContent = `Tracks (${results.tracks.length})`;
                el.appendChild(h);
                results.tracks.forEach((t, i) => {
                    const div = this._createTrackItem(t, () => {
                        Player.play(t, results.tracks, i);
                    });
                    el.appendChild(div);
                });
            }

            if (results.artists.length === 0 && results.albums.length === 0 && results.tracks.length === 0) {
                el.innerHTML = '<div class="empty-state">No results found</div>';
            }
        } catch (e) {
            el.innerHTML = `<div class="empty-state">Search error: ${e.message}</div>`;
        }
    },

    // --- UI Helpers ---

    _createListItem(icon, title, meta, coverPath, onClick) {
        const div = document.createElement('div');
        div.className = 'list-item';

        if (coverPath) {
            const cover = document.createElement('div');
            cover.className = 'item-cover';
            const img = document.createElement('img');
            img.src = API.coverUrl(coverPath, 'small');
            img.onerror = () => { cover.innerHTML = icon || this._icon('tracks'); };
            cover.appendChild(img);
            div.appendChild(cover);
        } else if (icon) {
            const cover = document.createElement('div');
            cover.className = 'item-cover';
            cover.innerHTML = icon;
            div.appendChild(cover);
        }

        const info = document.createElement('div');
        info.className = 'item-info';
        info.innerHTML = `<div class="item-title">${this._esc(title)}</div>`;
        if (meta) info.innerHTML += `<div class="item-meta">${this._esc(meta)}</div>`;
        div.appendChild(info);

        if (onClick) div.addEventListener('click', onClick);
        return div;
    },

    _createTrackItem(track, onClick, showTrackNum) {
        const div = document.createElement('div');
        div.className = 'list-item';

        // Track number or cover
        const cover = document.createElement('div');
        cover.className = 'item-cover';
        if (showTrackNum && track.track_num) {
            cover.innerHTML = `<span class="item-cover-placeholder" style="font-family:var(--font-mono);font-size:0.7rem">${track.track_num}</span>`;
        } else {
            const img = document.createElement('img');
            img.src = API.coverUrl(track.path, 'small');
            img.onerror = () => { cover.innerHTML = this._icon('tracks'); };
            cover.appendChild(img);
        }
        div.appendChild(cover);

        const info = document.createElement('div');
        info.className = 'item-info';
        info.innerHTML = `<div class="item-title">${this._esc(track.title)}</div>
            <div class="item-meta">${this._esc(track.artist)}${track.album ? ' · ' + this._esc(track.album) : ''}</div>`;
        div.appendChild(info);

        if (track.duration_fmt) {
            const dur = document.createElement('span');
            dur.className = 'item-duration';
            dur.textContent = track.duration_fmt;
            div.appendChild(dur);
        }

        div.addEventListener('click', onClick);

        // Context menu
        div.addEventListener('contextmenu', (e) => {
            e.preventDefault();
            this._showTrackContextMenu(e, track);
        });

        return div;
    },

    _createSettingSelect(label, key, currentValue, options, onChange) {
        const div = document.createElement('div');
        div.className = 'settings-item';

        const labelEl = document.createElement('span');
        labelEl.className = 'settings-label';
        labelEl.textContent = label;
        div.appendChild(labelEl);

        const select = document.createElement('select');
        select.className = 'settings-select';
        options.forEach(opt => {
            const option = document.createElement('option');
            option.value = opt.value;
            option.textContent = opt.label;
            if (opt.value === currentValue) option.selected = true;
            select.appendChild(option);
        });
        select.addEventListener('change', async () => {
            await API.updateSetting(key, select.value);
            if (onChange) onChange(select.value);
            this.toast(`${label} updated`);
        });
        div.appendChild(select);

        return div;
    },

    // --- Context Menu ---

    _showContextMenu(e, items) {
        const menu = document.getElementById('context-menu');
        menu.innerHTML = '';
        items.forEach(item => {
            const btn = document.createElement('button');
            btn.textContent = item.label;
            btn.addEventListener('click', (ev) => {
                ev.stopPropagation();
                menu.hidden = true;
                item.action();
            });
            menu.appendChild(btn);
        });
        menu.style.left = Math.min(e.clientX, window.innerWidth - 200) + 'px';
        menu.style.top = Math.min(e.clientY, window.innerHeight - items.length * 40) + 'px';
        menu.hidden = false;
    },

    _showTrackContextMenu(e, track) {
        const items = [
            { label: 'Play Next', action: () => {
                Player.addToQueue(track);
                this.toast('Added to queue');
            }},
            { label: 'Toggle Favorite', action: async () => {
                const r = await API.toggleFavorite('track', track.path);
                this.toast(r.favorited ? 'Added to favorites' : 'Removed from favorites');
            }},
        ];

        // Add to playlist submenu
        if (this.playlists.length > 0) {
            this.playlists.forEach(p => {
                items.push({
                    label: `Add to "${p.name}"`,
                    action: async () => {
                        await API.addToPlaylist(p.id, track.path);
                        this.toast(`Added to ${p.name}`);
                    },
                });
            });
        }

        this._showContextMenu(e, items);
    },

    // --- User Menu ---

    _showUserMenu() {
        const btn = document.getElementById('user-menu-btn');
        const rect = btn.getBoundingClientRect();
        const items = [
            { label: `Signed in as ${this.user.username}`, action: () => {} },
            { label: 'Log Out', action: async () => { await API.logout(); window.location.href = '/login'; } },
        ];

        this._showContextMenu({ clientX: rect.right - 200, clientY: rect.bottom }, items);
    },

    // --- Modals ---

    showModal(title, bodyHtml, actions) {
        document.getElementById('modal-title').textContent = title;
        document.getElementById('modal-body').innerHTML = bodyHtml;
        const actionsEl = document.getElementById('modal-actions');
        actionsEl.innerHTML = '';
        actions.forEach(a => {
            const btn = document.createElement('button');
            btn.textContent = a.label;
            if (a.danger) btn.className = 'danger';
            btn.addEventListener('click', () => {
                a.action();
            });
            actionsEl.appendChild(btn);
        });
        document.getElementById('modal-overlay').hidden = false;
    },

    closeModal() {
        document.getElementById('modal-overlay').hidden = true;
    },

    _showCreatePlaylistModal() {
        this.showModal('New Playlist',
            `<div class="form-group">
                <label for="pl-name">Playlist Name</label>
                <input type="text" id="pl-name">
            </div>`,
            [
                { label: 'Cancel', action: () => this.closeModal() },
                { label: 'Create', action: async () => {
                    const name = document.getElementById('pl-name').value.trim();
                    if (!name) return;
                    await API.createPlaylist(name);
                    this.closeModal();
                    this.toast('Playlist created');
                    this.navigate('playlists');
                }},
            ]
        );
        setTimeout(() => document.getElementById('pl-name')?.focus(), 100);
    },

    _showRenamePlaylistModal(playlist) {
        this.showModal('Rename Playlist',
            `<div class="form-group">
                <label for="pl-rename">Name</label>
                <input type="text" id="pl-rename" value="${this._esc(playlist.name)}">
            </div>`,
            [
                { label: 'Cancel', action: () => this.closeModal() },
                { label: 'Rename', action: async () => {
                    const name = document.getElementById('pl-rename').value.trim();
                    if (!name) return;
                    await API.renamePlaylist(playlist.id, name);
                    this.closeModal();
                    this.toast('Playlist renamed');
                    this.navigate('playlists');
                }},
            ]
        );
    },

    _showChangePasswordModal() {
        this.showModal('Change Password',
            `<div class="form-group">
                <label for="pw-current">Current Password</label>
                <input type="password" id="pw-current">
            </div>
            <div class="form-group">
                <label for="pw-new">New Password</label>
                <input type="password" id="pw-new">
            </div>`,
            [
                { label: 'Cancel', action: () => this.closeModal() },
                { label: 'Change', action: async () => {
                    const current = document.getElementById('pw-current').value;
                    const newPw = document.getElementById('pw-new').value;
                    if (!current || !newPw) return;
                    try {
                        await API.changePassword(current, newPw);
                        this.closeModal();
                        this.toast('Password changed');
                    } catch (e) {
                        this.toast(e.message);
                    }
                }},
            ]
        );
    },

    _showCreateUserModal() {
        this.showModal('Create User',
            `<div class="form-group">
                <label for="new-username">Username</label>
                <input type="text" id="new-username">
            </div>
            <div class="form-group">
                <label for="new-display">Display Name</label>
                <input type="text" id="new-display">
            </div>
            <div class="form-group">
                <label for="new-password">Password</label>
                <input type="password" id="new-password">
            </div>
            <div class="form-group checkbox-group">
                <input type="checkbox" id="new-admin">
                <label for="new-admin" style="margin-bottom:0">Admin</label>
            </div>`,
            [
                { label: 'Cancel', action: () => this.closeModal() },
                { label: 'Create', action: async () => {
                    const username = document.getElementById('new-username').value.trim();
                    const display = document.getElementById('new-display').value.trim();
                    const password = document.getElementById('new-password').value;
                    const isAdmin = document.getElementById('new-admin').checked;
                    if (!username || !password) { this.toast('Username and password required'); return; }
                    try {
                        await API.adminCreateUser({
                            username, display_name: display || username, password, is_admin: isAdmin,
                        });
                        this.closeModal();
                        this.toast('User created');
                        this.navigate('admin');
                    } catch (e) {
                        this.toast(e.message);
                    }
                }},
            ]
        );
    },

    _showResetPasswordModal(user) {
        this.showModal(`Reset Password: ${user.username}`,
            `<div class="form-group">
                <label for="reset-pw">New Password</label>
                <input type="password" id="reset-pw">
            </div>`,
            [
                { label: 'Cancel', action: () => this.closeModal() },
                { label: 'Reset', action: async () => {
                    const pw = document.getElementById('reset-pw').value;
                    if (!pw) return;
                    try {
                        await API.adminUpdateUser(user.id, { password: pw });
                        this.closeModal();
                        this.toast('Password reset');
                    } catch (e) {
                        this.toast(e.message);
                    }
                }},
            ]
        );
    },

    // --- Theme ---

    async _applyTheme() {
        try {
            const settings = await API.settings();
            const theme = settings.theme || 'dark';
            document.documentElement.dataset.theme = theme;
            const meta = document.querySelector('meta[name="theme-color"]');
            if (meta) meta.content = theme === 'dark' ? '#121218' : '#e9e3d3';
        } catch {}
    },

    // --- Toast ---

    toast(message) {
        const el = document.getElementById('toast');
        el.textContent = message;
        el.classList.add('visible');
        setTimeout(() => el.classList.remove('visible'), 2000);
    },

    // --- Track Change Callback ---

    onTrackChange(track) {
        // Update page title
        document.title = `${track.title} — PaperJam`;

        // Load playlists for context menu
        API.playlists().then(p => { this.playlists = p; }).catch(() => {});
    },

    // --- Icon Helper ---

    _icon(name, size = 16) {
        const url = `/static/icons/ui/bm_${name}_${size}.png`;
        return `<span class="icon${size !== 16 ? ` icon-${size}` : ''}" style="-webkit-mask-image:url(${url});mask-image:url(${url})"></span>`;
    },

    // --- Escape HTML ---

    _esc(s) {
        if (!s) return '';
        const d = document.createElement('div');
        d.textContent = s;
        return d.innerHTML;
    },
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => App.init());
