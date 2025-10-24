let selectedEmployee = null;
const employeeCache = new Map();
let searchCache = new Map();

// Lightweight initialization - no bulk data loading
async function loadFlaskData() {
    try {
        console.log('Application initialized - using server-side search');
        // No bulk data loading - use search API instead
    } catch (error) {
        console.error('Initialization error:', error);
    }
}

function getInitials(name) {
    if (!name) return 'NA';
    return name.split(' ').map(word => word.charAt(0).toUpperCase()).join('').substring(0, 2);
}

function isValidImageUrl(url) {
    return url && url.trim() !== '' && (url.startsWith('http://') || url.startsWith('https://'));
}

// Removed - no longer needed with server-side search

function createEmployeeCard(employee, isTarget = false, stepCount = null, connectionStrength = null) {
    if (!employee) return document.createElement("div");

    const isQtEmployee = employee.company === "QT";

    const card = document.createElement("div");
    card.className = `employee-card ${isTarget ? "target-card" : "qt-card"}`;
    
    const stepBadge = stepCount !== null && stepCount > 0
        ? `<div class="step-badge">${stepCount}</div>`
        : "";

    const strengthBadge = connectionStrength
        ? `<div class="connection-strength-badge strength-${connectionStrength.toLowerCase()}">${connectionStrength}</div>`
        : "";

    let avatarHtml = '';
    const avatarBaseClasses = "w-16 h-16 rounded-full mb-3 border-2 border-gray-300 shadow flex items-center justify-center font-bold text-xl mx-auto";
    const initialsTextClasses = "text-gray-600";

    if (isQtEmployee) {
        avatarHtml = `<div class="${avatarBaseClasses} bg-gradient-to-br from-blue-100 to-purple-100"><span class="${initialsTextClasses}">${getInitials(employee.name)}</span></div>`;
    } else {
        avatarHtml = isValidImageUrl(employee.avatar)
            ? `<img src="${employee.avatar}" alt="${employee.name}" class="w-16 h-16 rounded-full mb-3 object-cover mx-auto border-2 border-gray-200" onError="this.style.display='none'; this.nextElementSibling.style.display='flex';">
               <div class="${avatarBaseClasses} bg-gradient-to-br from-blue-100 to-purple-100" style="display:none;"><span class="${initialsTextClasses}">${getInitials(employee.name)}</span></div>`
            : `<div class="${avatarBaseClasses} bg-gradient-to-br from-blue-100 to-purple-100"><span class="${initialsTextClasses}">${getInitials(employee.name)}</span></div>`;
    }
    
    const organisationText = isQtEmployee ? "" : `<p class="text-xs font-semibold uppercase tracking-wider text-gray-500 mb-1">${employee.organisation || employee.company}</p>`;

    card.innerHTML = `
        ${stepBadge}
        ${strengthBadge}
        <div class="flex flex-col items-center text-center justify-center h-full p-4">
            ${avatarHtml}
            ${organisationText}
            <h4 class="font-bold text-sm text-gray-800 mb-1">${employee.name}</h4>
            <p class="text-xs text-gray-600 mb-1">${employee.designation}</p>
            <p class="text-xs text-gray-400 font-mono">${employee.ldap}</p>
        </div>`;
    
    return card;
}

async function getConnectionsForEmployee(employee) {
    console.log('Fetching connections for employee:', employee.name, employee.ldap);

    try {
        const response = await fetch(`/api/connections/${employee.ldap}`);
        if (!response.ok) {
            console.warn('Failed to fetch connections from API');
            return [];
        }
        const connections = await response.json();
        console.log('Total connections found for', employee.name, ':', connections.length);
        return connections;
    } catch (error) {
        console.error('Error fetching connections:', error);
        return [];
    }
}

function findQTEmployee(qtLdap, qtName, qtEmail) {
    // Return a lightweight QT employee object based on connection data
    if (qtName && qtLdap) {
        return {
            ldap: qtLdap,
            name: qtName,
            email: qtEmail || qtLdap + '@qualitest.com',
            company: "QT",
            designation: "QT Team Member",
            organisation: "QT Team",
            avatar: 'https://i.pravatar.cc/150?u=' + qtLdap
        };
    }

    return null;
}

// Simplified: Use backend API for connection discovery
async function findHierarchicalConnections(targetEmployee) {
    try {
        // Backend handles all connection logic now
        const connections = await getConnectionsForEmployee(targetEmployee);

        if (connections.length > 0) {
            return [{
                path: [targetEmployee],
                connections: connections,
                stepCount: 0
            }];
        }

        return [];
    } catch (error) {
        console.error('Error finding connections:', error);
        return [];
    }
}

function renderNoConnections(employee) {
    const content = document.createElement('div');
    content.innerHTML = `
        <div class="flex justify-center mb-16">
            ${createEmployeeCard(employee, true).outerHTML}
        </div>
        <div class="text-center">
            <p class="text-gray-600 font-medium mb-8">No direct connections found</p>
            <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-6 max-w-md mx-auto">
                <h3 class="font-semibold text-yellow-900 mb-2">No QT Connections</h3>
                <p class="text-sm text-yellow-800">No declared connections found for ${employee.name}. Consider exploring their network or declaring new connections.</p>
            </div>
        </div>`;
    return content;
}

// MODIFIED: renderConnectionPaths to display hierarchical paths
async function renderConnectionPaths(employee) {
    console.log('Rendering connection paths for:', employee);
    const content = document.createElement("div");
    content.className = "dotted-bg min-h-screen p-8";

    const hierarchicalPaths = await findHierarchicalConnections(employee);

    if (hierarchicalPaths.length > 0) {
        hierarchicalPaths.forEach(pathData => {
            const pathContainer = document.createElement("div");
            pathContainer.className = "mb-16";

            // Display the path (employee -> manager -> ...)
            const employeePathDiv = document.createElement("div");
            employeePathDiv.className = "flex flex-col items-center";
            pathData.path.forEach((emp, index) => {
                employeePathDiv.appendChild(createEmployeeCard(emp, index === 0));
                if (index < pathData.path.length - 1) {
                    const connector = document.createElement("div");
                    connector.className = "w-0.5 h-8 bg-gray-300 my-2"; // Vertical line connector
                    employeePathDiv.appendChild(connector);
                }
            });
            pathContainer.appendChild(employeePathDiv);

            // Add a connector between the last employee in the path and the QT connections
            const connectorToQt = document.createElement("div");
            connectorToQt.className = "w-0.5 h-8 bg-gray-300 my-2 mx-auto"; // Vertical line connector
            pathContainer.appendChild(connectorToQt);

            // Display the connections to QT team members
            const qtSection = document.createElement("div");
            qtSection.className = "flex justify-center gap-8 flex-wrap mt-8";
            pathData.connections.forEach((conn) => {
                // Backend returns qtLdap, not 'QT Employee LDAP'
                const qtEmployee = findQTEmployee(
                    conn.qtLdap || conn['QT Employee LDAP'],
                    conn.qtName || conn['QT Employee Name'],
                    conn.qtEmail || conn['QT Employee Email']
                );
                if (qtEmployee) {
                    const strength = conn.connectionStrength || conn['Connection Strength'];
                    const qtCard = createEmployeeCard(qtEmployee, false, pathData.stepCount + 1, strength);
                    qtSection.appendChild(qtCard);
                }
            });
            pathContainer.appendChild(qtSection);
            content.appendChild(pathContainer);
        });
    } else {
        console.log('No connections found, showing no connections message');
        content.innerHTML = 
            '<div class="flex justify-center mb-16">' +
                createEmployeeCard(employee, true).outerHTML +
            '</div>' +
            '<div class="text-center">' +
                '<p class="text-gray-600 font-medium mb-8">No direct or hierarchical connections found</p>' +
                '<div class="bg-yellow-50 border border-yellow-200 rounded-lg p-6 max-w-md mx-auto">' +
                    '<h3 class="font-semibold text-yellow-900 mb-2">No QT Connections</h3>' +
                    '<p class="text-sm text-yellow-800">No declared connections found for ' + employee.name + '. Consider exploring their network or declaring new connections.</p>' +
                '</div>' +
            '</div>';
    }

    return content;
}

async function showSelectedEmployee() {
    if (!selectedEmployee) return;
    const mainContent = document.getElementById("mainContent");
    
    mainContent.innerHTML = '<div class="text-center py-16"><div class="animate-spin rounded-full h-8 w-8 border-b-2 border-gray-900 mx-auto"></div><p class="mt-4 text-gray-500">Loading connection paths...</p></div>';

    try {
        const pathContent = await renderConnectionPaths(selectedEmployee);
        mainContent.innerHTML = "";
        mainContent.appendChild(pathContent);
        if (typeof lucide !== 'undefined' && typeof lucide.createIcons === 'function') {
            try {
                lucide.createIcons();
            } catch (lucideError) {
                console.warn('Lucide icons initialization failed:', lucideError);
            }
        }
    } catch (error) {
        console.error('Error showing selected employee:', error);
        mainContent.innerHTML = `<div class="text-center py-16"><p class="text-red-500">Error loading connection paths</p><p class="text-sm text-gray-500 mt-2">${error.message}</p></div>`;
    }
}

function renderSuggestionItem(employee) {
    const item = document.createElement("button");
    item.className = "suggestion-item";
    
    const avatarHtml = isValidImageUrl(employee.avatar)
        ? `<img src="${employee.avatar}" alt="${employee.name}" class="w-10 h-10 rounded-full object-cover" onError="this.style.display='none'; this.nextElementSibling.style.display='flex';"><div class="w-10 h-10 rounded-full bg-blue-500 text-white flex items-center justify-center font-bold text-sm" style="display:none;">${getInitials(employee.name)}</div>`
        : `<div class="w-10 h-10 rounded-full bg-blue-500 text-white flex items-center justify-center font-bold text-sm">${getInitials(employee.name)}</div>`;
    
    item.innerHTML = `
        <div class="flex items-center space-x-3 flex-1">
            ${avatarHtml}
            <div class="flex-1 text-left">
                <div class="font-medium">${employee.name}</div>
                <div class="text-sm text-gray-500">${employee.designation}</div>
                <div class="text-xs text-gray-400">${employee.ldap}</div>
            </div>
        </div>`;
    
    item.addEventListener("click", async () => {
        const searchInput = document.getElementById("searchInput");
        const suggestions = document.getElementById("suggestions");
        searchInput.value = employee.name;
        suggestions.classList.add("hidden");
        selectedEmployee = employee;
        await showSelectedEmployee();
    });

    return item;
}

function setupSearch() {
    const searchInput = document.getElementById("searchInput");
    const suggestions = document.getElementById("suggestions");
    let searchTimeout;

    searchInput.addEventListener("input", async (e) => {
        const searchTerm = e.target.value.trim();

        // Clear previous timeout
        if (searchTimeout) {
            clearTimeout(searchTimeout);
        }

        if (searchTerm.length === 0) {
            suggestions.classList.add("hidden");
            selectedEmployee = null;
            resetToOriginalState();
            return;
        }

        if (searchTerm.length < 2) {
            suggestions.innerHTML = '<div class="p-4 text-gray-500 text-sm">Type at least 2 characters...</div>';
            suggestions.classList.remove("hidden");
            return;
        }

        // Debounce search by 300ms
        searchTimeout = setTimeout(async () => {
            try {
                // Show loading state
                suggestions.innerHTML = '<div class="p-4 text-gray-500 text-sm">Searching...</div>';
                suggestions.classList.remove("hidden");

                // Use backend search API
                const response = await fetch(`/api/search-employees?q=${encodeURIComponent(searchTerm)}`);
                if (!response.ok) {
                    throw new Error('Search failed');
                }

                const filtered = await response.json();

                suggestions.innerHTML = "";
                if (filtered.length > 0) {
                    filtered.forEach((employee) => {
                        const item = renderSuggestionItem(employee);
                        suggestions.appendChild(item);
                    });
                    suggestions.classList.remove("hidden");
                } else {
                    suggestions.innerHTML = '<div class="p-4 text-gray-500 text-sm">No results found</div>';
                    suggestions.classList.remove("hidden");
                }
            } catch (error) {
                console.error('Search error:', error);
                suggestions.innerHTML = '<div class="p-4 text-red-500 text-sm">Search error. Please try again.</div>';
                suggestions.classList.remove("hidden");
            }
        }, 300);
    });

    document.addEventListener("click", (e) => {
        if (!e.target.closest(".relative")) suggestions.classList.add("hidden");
    });
}

function resetToOriginalState() {
    const mainContent = document.getElementById("mainContent");
    mainContent.innerHTML = '<div class="text-center text-gray-500 py-16"><p>Search and select a Google employee to find the shortest connection path from the QT team.</p></div>';
    selectedEmployee = null;
}

async function init() {
    console.log('Initializing Qonnect - using server-side search...');
    await loadFlaskData();

    setupSearch();
    if (typeof lucide !== 'undefined' && typeof lucide.createIcons === 'function') {
        try {
            lucide.createIcons();
        } catch (lucideError) {
            console.warn('Lucide icons initialization failed:', lucideError);
        }
    }
    console.log('Initialization complete! Ready for searches.');
}

document.addEventListener("DOMContentLoaded", init);