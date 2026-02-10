/* PaperJam Web — API Client */

const API = {
    async _fetch(url, opts = {}) {
        const res = await fetch(url, {
            ...opts,
            headers: { 'Content-Type': 'application/json', ...opts.headers },
        });
        if (res.status === 401) {
            window.location.href = '/login';
            throw new Error('Not authenticated');
        }
        if (!res.ok) {
            const err = await res.json().catch(() => ({ detail: res.statusText }));
            throw new Error(err.detail || 'Request failed');
        }
        return res.json();
    },

    // Auth
    me() { return this._fetch('/auth/me'); },
    logout() { return this._fetch('/auth/logout', { method: 'POST' }); },
    changePassword(current, newPw) {
        return this._fetch('/auth/change-password', {
            method: 'POST',
            body: JSON.stringify({ current_password: current, new_password: newPw }),
        });
    },

    // Library
    libraryStats() { return this._fetch('/api/library/stats'); },
    artists() { return this._fetch('/api/library/artists'); },
    artist(name) { return this._fetch(`/api/library/artists/${encodeURIComponent(name)}`); },
    albums() { return this._fetch('/api/library/albums'); },
    album(name) { return this._fetch(`/api/library/albums/${encodeURIComponent(name)}`); },
    tracks() { return this._fetch('/api/library/tracks'); },
    search(q) { return this._fetch(`/api/library/search?q=${encodeURIComponent(q)}`); },
    scanLibrary() { return this._fetch('/api/library/scan', { method: 'POST' }); },

    // Streaming
    streamUrl(path, quality) {
        const encoded = btoa(unescape(encodeURIComponent(path)))
            .replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
        // Use URL-safe base64
        const urlSafeEncoded = this._urlSafeBase64(path);
        return `/api/stream/${urlSafeEncoded}?quality=${quality || 'high'}`;
    },

    coverUrl(path, size) {
        const encoded = this._urlSafeBase64(path);
        return `/api/cover/${encoded}?size=${size || 'medium'}`;
    },

    _urlSafeBase64(str) {
        // Encode string to URL-safe base64
        const bytes = new TextEncoder().encode(str);
        let binary = '';
        for (const b of bytes) binary += String.fromCharCode(b);
        return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_');
    },

    // Favorites
    favorites(type) {
        const params = type ? `?item_type=${type}` : '';
        return this._fetch(`/api/favorites${params}`);
    },
    toggleFavorite(type, key) {
        return this._fetch('/api/favorites/toggle', {
            method: 'POST',
            body: JSON.stringify({ item_type: type, item_key: key }),
        });
    },
    checkFavorite(type, key) {
        return this._fetch(`/api/favorites/check?item_type=${type}&item_key=${encodeURIComponent(key)}`);
    },

    // Playlists
    playlists() { return this._fetch('/api/playlists'); },
    playlist(id) { return this._fetch(`/api/playlists/${id}`); },
    createPlaylist(name) {
        return this._fetch('/api/playlists', {
            method: 'POST',
            body: JSON.stringify({ name }),
        });
    },
    renamePlaylist(id, name) {
        return this._fetch(`/api/playlists/${id}`, {
            method: 'PUT',
            body: JSON.stringify({ name }),
        });
    },
    deletePlaylist(id) {
        return this._fetch(`/api/playlists/${id}`, { method: 'DELETE' });
    },
    addToPlaylist(id, trackPath) {
        return this._fetch(`/api/playlists/${id}/tracks`, {
            method: 'POST',
            body: JSON.stringify({ track_path: trackPath }),
        });
    },
    removeFromPlaylist(playlistId, trackId) {
        return this._fetch(`/api/playlists/${playlistId}/tracks/${trackId}`, { method: 'DELETE' });
    },

    // Recents
    recents(limit) {
        const params = limit ? `?limit=${limit}` : '';
        return this._fetch(`/api/recents${params}`);
    },

    // Settings
    settings() { return this._fetch('/api/settings'); },
    updateSetting(key, value) {
        return this._fetch('/api/settings', {
            method: 'PUT',
            body: JSON.stringify({ key, value }),
        });
    },

    // Admin
    adminUsers() { return this._fetch('/api/admin/users'); },
    adminCreateUser(data) {
        return this._fetch('/api/admin/users', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },
    adminUpdateUser(id, data) {
        return this._fetch(`/api/admin/users/${id}`, {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    },
    adminDeleteUser(id) {
        return this._fetch(`/api/admin/users/${id}`, { method: 'DELETE' });
    },
};
