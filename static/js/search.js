let googleEmployees = [];
let coreTeam = [];
let selectedEmployee = null;
let connectionData = [];
const employeeMap = new Map();
let coreTeamMap = new Map();

async function loadFlaskData() {
    try {
        console.log('Loading data from Flask API...');
        
        const googleResponse = await fetch('/api/google-employees');
        if (googleResponse.ok) {
            const data = await googleResponse.json();
            googleEmployees = data.map(emp => ({
                ldap: emp.ldap,
                email: emp.email || emp.ldap + '@google.com',
                avatar: emp['MOMA Photo URL'] || emp.avatar || null,
                name: emp.name,
                company: emp.company || "GOOGLE",
                designation: emp.designation,
                organisation: emp.organisation || emp.department || "Google",
                manager: emp.manager || null,
            }));
        }

        const qtResponse = await fetch('/api/qt-team');
        if (qtResponse.ok) {
            const qtData = await qtResponse.json();
            coreTeam = qtData.map(emp => ({
                ldap: emp.ldap,
                email: emp.email || emp.ldap + '@qualitestgroup.com',
                avatar: emp.avatar || 'https://i.pravatar.cc/150?u=' + emp.ldap,
                name: emp.name,
                company: emp.company || "QT",
                designation: emp.designation,
                organisation: emp.organisation || emp.department || "QT",
            }));
            coreTeam.forEach(emp => coreTeamMap.set(emp.ldap, emp));
        }

        const connectionsResponse = await fetch('/api/connections-from-sheets');
        if (connectionsResponse.ok) {
            const sheetsData = await connectionsResponse.json();
            connectionData = sheetsData.connections || [];
        }
        
        console.log('API data loaded successfully');
        
    } catch (error) {
        console.log('API not available, using sample data');
        googleEmployees = sampleGoogleEmployees;
        coreTeam = sampleCoreTeam;
        coreTeam.forEach(emp => coreTeamMap.set(emp.ldap, emp));
        connectionData = sampleConnectionData;
    }
}

function getInitials(name) {
    if (!name) return 'NA';
    return name.split(' ').map(word => word.charAt(0).toUpperCase()).join('').substring(0, 2);
}

function isValidImageUrl(url) {
    return url && url.trim() !== '' && (url.startsWith('http://') || url.startsWith('https://'));
}

function updateEmployeeMap() {
    employeeMap.clear();
    googleEmployees.forEach((e) => employeeMap.set(e.ldap, e));
    coreTeam.forEach((e) => employeeMap.set(e.ldap, e));
}

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

function getConnectionsForEmployee(employee) {
    console.log('Looking for connections for employee:', employee.name, employee.ldap, employee.email);
    
    const connections = connectionData.filter(conn => {
        const googleLdap = (conn['Google Employee LDAP'] || '').trim().toLowerCase();
        const googleEmail = (conn['Google Employee Email'] || '').trim().toLowerCase();
        const googleName = (conn['Google Employee Name'] || '').trim().toLowerCase();
        
        const empLdap = (employee.ldap || '').trim().toLowerCase();
        const empEmail = (employee.email || '').trim().toLowerCase();
        const empName = (employee.name || '').trim().toLowerCase();
        
        const match = googleLdap === empLdap || 
                     googleEmail === empEmail ||
                     googleName === empName ||
                     (googleLdap && empLdap && googleLdap.includes(empLdap)) ||
                     (empLdap && googleLdap && empLdap.includes(googleLdap));
        
        if (match) {
            console.log('Connection found:', conn);
        }
        
        return match;
    });
    
    console.log('Total connections found for', employee.name, ':', connections.length);
    return connections;
}

function findQTEmployee(qtLdap, qtName, qtEmail) {
    let qtEmployee = coreTeamMap.get(qtLdap);
    
    if (qtEmployee) {
        return qtEmployee;
    }
    
    // Fallback to iterating if not found by LDAP (e.g., if qtLdap was not the primary key in coreTeamMap)
    qtEmployee = coreTeam.find((e) => 
        e.email === qtEmail || 
        e.name === qtName
    );

    if (qtEmployee) {
        return qtEmployee;
    }
    
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

// NEW: Function to find hierarchical connections
async function findHierarchicalConnections(targetEmployee) {
    const directConnections = getConnectionsForEmployee(targetEmployee);
    if (directConnections.length > 0) {
        return [{
            path: [targetEmployee],
            connections: directConnections,
            stepCount: 0 // Direct connection
        }];
    }

    // If no direct connections, try through managers
    const hierarchyResponse = await fetch(`/api/hierarchy/${targetEmployee.ldap}`);
    if (!hierarchyResponse.ok) {
        console.error('Failed to fetch hierarchy for', targetEmployee.ldap);
        return [];
    }
    const hierarchyData = await hierarchyResponse.json();
    const managerChain = hierarchyData.manager_chain || [];

    const hierarchicalPaths = [];

    for (let i = 0; i < managerChain.length; i++) {
        const manager = managerChain[i];
        const managerConnections = getConnectionsForEmployee(manager);
        if (managerConnections.length > 0) {
            hierarchicalPaths.push({
                path: [targetEmployee, ...managerChain.slice(0, i + 1)],
                connections: managerConnections,
                stepCount: i + 1 // Number of managers in between
            });
        }
    }
    return hierarchicalPaths;
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
                const qtEmployee = findQTEmployee(
                    conn['QT Employee LDAP'], 
                    conn['QT Employee Name'], 
                    conn['QT Employee Email']
                );
                if (qtEmployee) {
                    const qtCard = createEmployeeCard(qtEmployee, false, pathData.stepCount + 1, conn['Connection Strength']);
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
        lucide.createIcons();
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

    searchInput.addEventListener("input", async (e) => {
        const searchTerm = e.target.value.toLowerCase();
        
        if (searchTerm.length === 0) {
            suggestions.classList.add("hidden");
            selectedEmployee = null;
            resetToOriginalState();
            return;
        }

        let filtered = googleEmployees
            .filter(emp =>
                emp.name.toLowerCase().includes(searchTerm) || 
                emp.ldap.toLowerCase().includes(searchTerm) || 
                emp.designation.toLowerCase().includes(searchTerm)
            )
            .slice(0, 20);

        suggestions.innerHTML = "";
        if (filtered.length > 0) {
            filtered.forEach((employee) => {
                const item = renderSuggestionItem(employee);
                suggestions.appendChild(item);
            });
            suggestions.classList.remove("hidden");
        } else {
            suggestions.classList.add("hidden");
        }
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
    console.log('Initializing Qonnect...');
    await loadFlaskData();
    updateEmployeeMap();
    
    console.log('Data loaded:');
    console.log('- Google employees:', googleEmployees.length);
    console.log('- QT team:', coreTeam.length);
    console.log('- Connections:', connectionData.length);
    
    setupSearch();
    lucide.createIcons();
    console.log('Initialization complete!');
}

document.addEventListener("DOMContentLoaded", init);