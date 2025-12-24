// document.addEventListener('DOMContentLoaded', (event) => {
//     // const socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);
//     const socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port, {
//     transports: ['websocket', 'polling']
// });
//     socket.on('connect', function() {
//         console.log('Socket.IO connected');
//     });

//     socket.on('log', function(msg) {
//         const logs = document.getElementById('logs');
//         logs.textContent += msg.data + '\n';
//         // Scroll to the bottom of the log container
//         logs.scrollTop = logs.scrollHeight;
//     });
// });

document.addEventListener('DOMContentLoaded', (event) => {
    const socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port, {
        transports: ['websocket', 'polling']
    });

    socket.on('connect', function() {
        console.log('Socket.IO connected');
    });

    socket.on('log', function(msg) {
        const logs = document.getElementById('logs');
        logs.textContent += msg.data + '\n';
        logs.scrollTop = logs.scrollHeight;
    });

    socket.on('connect_error', (err) => {
        console.error('Connection Error:', err);
    });

    socket.on('disconnect', () => {
        console.warn('Socket disconnected');
    });
});

document.getElementById('extractor-form').addEventListener('submit', async function(event) {
    event.preventDefault();

    const url = document.getElementById('url').value.trim();
    const login_url = document.getElementById('login_url') ? document.getElementById('login_url').value.trim() : '';
    const username = document.getElementById('username').value.trim();
    const password = document.getElementById('password').value.trim();
    // const headless = document.getElementById('headless').checked;

    const spinner = document.getElementById('spinner');
    const resultsContainer = document.getElementById('results-container');
    const resultMessage = document.getElementById('result-message');
    const results = document.getElementById('results');
    const downloadLink = document.getElementById('download-link');
    const logContainer = document.getElementById('log-container');
    const logs = document.getElementById('logs');

    spinner.style.display = 'block';
    resultsContainer.style.display = 'none';
    downloadLink.style.display = 'none';
    logContainer.style.display = 'block';
    logs.textContent = ''; // Clear previous logs

    try {
        // ✅ include username and password in payload
        const response = await fetch('/extract', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, login_url, username, password})
        });

        const data = await response.json();

        if (response.ok) {
            resultMessage.textContent = `✅ Found ${data.links.length} header links:`;
            results.textContent = JSON.stringify(data.links, null, 2);
            resultsContainer.style.display = 'block';

            // Enable Zip download
            if (data.zip_file) {
                downloadLink.href = `/download/${data.zip_file}`;
                downloadLink.download = data.zip_file;
                downloadLink.textContent = `⬇️ Download ${data.zip_file}`;
                downloadLink.style.display = 'inline-block';
            }
        } else {
            resultMessage.textContent = `❌ Error: ${data.error}`;
            results.textContent = '';
            resultsContainer.style.display = 'block';
        }
    } catch (error) {
        resultMessage.textContent = `❌ Network Error: ${error.message}`;
        results.textContent = '';
        resultsContainer.style.display = 'block';
    } finally {
        spinner.style.display = 'none';
    }
});
