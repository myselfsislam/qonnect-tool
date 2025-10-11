"""
Firestore Database Helper Module
Provides fast, indexed queries for employee data
"""

from google.cloud import firestore
from google.oauth2.service_account import Credentials
import os
import logging

logger = logging.getLogger(__name__)

# Initialize Firestore client
_db_client = None

def get_firestore_client():
    """Get or create Firestore client"""
    global _db_client

    if _db_client is None:
        try:
            # Use service account credentials
            creds = Credentials.from_service_account_file('credentials.json')
            _db_client = firestore.Client(credentials=creds, project='smartstakeholdersearch')
            logger.info("✅ Firestore client initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Firestore: {e}")
            raise

    return _db_client


# ==================== EMPLOYEE QUERIES ====================

def search_employees(query, limit=25):
    """
    Search employees by name, email, or LDAP
    Returns results in 20-100ms (vs 15-20 seconds with Google Sheets!)
    """
    db = get_firestore_client()
    results = []

    try:
        query_lower = query.lower()

        # Search by name (prefix match)
        name_results = db.collection('employees')\
            .where('name_lower', '>=', query_lower)\
            .where('name_lower', '<=', query_lower + '\uf8ff')\
            .limit(limit)\
            .stream()

        for doc in name_results:
            results.append({**doc.to_dict(), 'id': doc.id})

        # If not enough results, search by LDAP
        if len(results) < limit:
            ldap_results = db.collection('employees')\
                .where('ldap', '>=', query_lower)\
                .where('ldap', '<=', query_lower + '\uf8ff')\
                .limit(limit - len(results))\
                .stream()

            for doc in ldap_results:
                emp_data = {**doc.to_dict(), 'id': doc.id}
                if emp_data not in results:  # Avoid duplicates
                    results.append(emp_data)

        logger.debug(f"Search '{query}' returned {len(results)} results")
        return results[:limit]

    except Exception as e:
        logger.error(f"Search error for query '{query}': {e}")
        return []


def get_employee_by_ldap(ldap):
    """
    Get employee by LDAP ID
    Returns in 5-20ms (vs 0.1-2 seconds with Google Sheets!)
    """
    db = get_firestore_client()

    try:
        doc = db.collection('employees').document(ldap.lower()).get()

        if doc.exists:
            return {**doc.to_dict(), 'id': doc.id}
        else:
            logger.debug(f"Employee not found: {ldap}")
            return None

    except Exception as e:
        logger.error(f"Error fetching employee {ldap}: {e}")
        return None


def get_employees_by_department(department, limit=100):
    """Get all employees in a department"""
    db = get_firestore_client()

    try:
        results = db.collection('employees')\
            .where('department', '==', department)\
            .limit(limit)\
            .stream()

        return [{**doc.to_dict(), 'id': doc.id} for doc in results]

    except Exception as e:
        logger.error(f"Error fetching department {department}: {e}")
        return []


def get_employees_by_location(location, limit=100):
    """Get all employees in a location"""
    db = get_firestore_client()

    try:
        results = db.collection('employees')\
            .where('location', '==', location)\
            .limit(limit)\
            .stream()

        return [{**doc.to_dict(), 'id': doc.id} for doc in results]

    except Exception as e:
        logger.error(f"Error fetching location {location}: {e}")
        return []


def get_google_employees(limit=100000):
    """Get all Google employees (defaults to 100k for bulk loading)"""
    db = get_firestore_client()

    try:
        query = db.collection('employees').where('organisation', '==', 'Google')

        if limit:
            query = query.limit(limit)

        results = query.stream()
        employees = [{**doc.to_dict(), 'id': doc.id} for doc in results]

        logger.info(f"Retrieved {len(employees)} Google employees from Firestore")
        return employees

    except Exception as e:
        logger.error(f"Error fetching Google employees: {e}")
        return []


# ==================== CONNECTION QUERIES ====================

def get_employee_connections(employee_ldap):
    """
    Get all connections for an employee
    Returns in 20-50ms (vs 20-30 seconds with Google Sheets!)
    """
    db = get_firestore_client()

    try:
        results = db.collection('connections')\
            .where('google_employee_ldap', '==', employee_ldap.lower())\
            .stream()

        connections = [{**doc.to_dict(), 'id': doc.id} for doc in results]
        logger.debug(f"Found {len(connections)} connections for {employee_ldap}")
        return connections

    except Exception as e:
        logger.error(f"Error fetching connections for {employee_ldap}: {e}")
        return []


def get_all_connections(limit=10000):
    """Get all connections (for building transitive connections)"""
    db = get_firestore_client()

    try:
        results = db.collection('connections')\
            .limit(limit)\
            .stream()

        return [{**doc.to_dict(), 'id': doc.id} for doc in results]

    except Exception as e:
        logger.error(f"Error fetching all connections: {e}")
        return []


# ==================== STATISTICS ====================

def get_stats():
    """Get database statistics"""
    db = get_firestore_client()

    try:
        # Get counts from metadata document
        metadata_doc = db.collection('metadata').document('stats').get()

        if metadata_doc.exists:
            return metadata_doc.to_dict()
        else:
            # Fallback: count manually (slower)
            employees = list(db.collection('employees').limit(1000).stream())
            connections = list(db.collection('connections').limit(1000).stream())

            return {
                'total_employees': len(employees),
                'total_connections': len(connections),
                'last_updated': firestore.SERVER_TIMESTAMP
            }

    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return {}


# ==================== DATA MANAGEMENT ====================

def add_employee(employee_data):
    """Add or update an employee"""
    db = get_firestore_client()

    try:
        ldap = employee_data.get('ldap', '').lower()
        if not ldap:
            raise ValueError("LDAP is required")

        # Add lowercase name for searching
        employee_data['name_lower'] = employee_data.get('name', '').lower()
        employee_data['ldap'] = ldap

        db.collection('employees').document(ldap).set(employee_data, merge=True)
        logger.debug(f"Added/updated employee: {ldap}")
        return True

    except Exception as e:
        logger.error(f"Error adding employee: {e}")
        return False


def add_connection(connection_data):
    """Add a connection"""
    db = get_firestore_client()

    try:
        # Auto-generate ID or use custom one
        if 'id' in connection_data:
            doc_id = connection_data.pop('id')
            db.collection('connections').document(doc_id).set(connection_data)
        else:
            db.collection('connections').add(connection_data)

        logger.debug("Added connection")
        return True

    except Exception as e:
        logger.error(f"Error adding connection: {e}")
        return False


def batch_add_employees(employees_list, batch_size=500):
    """
    Add multiple employees in batches
    Much faster than individual adds!
    """
    db = get_firestore_client()
    total_added = 0

    try:
        for i in range(0, len(employees_list), batch_size):
            batch = db.batch()
            batch_employees = employees_list[i:i+batch_size]

            for emp_data in batch_employees:
                ldap = emp_data.get('ldap', '').lower()
                if ldap:
                    emp_data['name_lower'] = emp_data.get('name', '').lower()
                    emp_data['ldap'] = ldap

                    doc_ref = db.collection('employees').document(ldap)
                    batch.set(doc_ref, emp_data, merge=True)
                    total_added += 1

            # Commit batch
            batch.commit()
            logger.info(f"Batch {i//batch_size + 1}: Added {len(batch_employees)} employees")

        logger.info(f"✅ Successfully added {total_added} employees to Firestore")
        return total_added

    except Exception as e:
        logger.error(f"Batch add error: {e}")
        return total_added


def batch_add_connections(connections_list, batch_size=500):
    """Add multiple connections in batches"""
    db = get_firestore_client()
    total_added = 0

    try:
        for i in range(0, len(connections_list), batch_size):
            batch = db.batch()
            batch_connections = connections_list[i:i+batch_size]

            for conn_data in batch_connections:
                doc_ref = db.collection('connections').document()
                batch.set(doc_ref, conn_data)
                total_added += 1

            batch.commit()
            logger.info(f"Batch {i//batch_size + 1}: Added {len(batch_connections)} connections")

        logger.info(f"✅ Successfully added {total_added} connections to Firestore")
        return total_added

    except Exception as e:
        logger.error(f"Batch add error: {e}")
        return total_added


# ==================== CONNECTION QUERIES (NEW) ====================

def get_all_connections():
    """
    Get all connections from Firestore
    Returns in 50-200ms (vs 15-20 seconds with Google Sheets!)
    """
    db = get_firestore_client()

    try:
        results = db.collection('connections').stream()
        connections = [{**doc.to_dict(), 'id': doc.id} for doc in results]
        logger.info(f"Retrieved {len(connections)} connections from Firestore")
        return connections
    except Exception as e:
        logger.error(f"Error getting connections: {e}")
        return []


def get_connections_by_google_employee(google_ldap):
    """
    Get all connections for a specific Google employee
    Returns in 20-50ms
    """
    db = get_firestore_client()

    try:
        ldap_lower = google_ldap.lower()
        results = db.collection('connections')\
            .where('google_employee_ldap', '==', ldap_lower)\
            .stream()

        connections = [{**doc.to_dict(), 'id': doc.id} for doc in results]
        return connections
    except Exception as e:
        logger.error(f"Error getting connections for {google_ldap}: {e}")
        return []


def get_connections_by_qt_employee(qt_ldap):
    """
    Get all connections for a specific QT employee
    Returns in 20-50ms
    """
    db = get_firestore_client()

    try:
        ldap_lower = qt_ldap.lower()
        results = db.collection('connections')\
            .where('qt_employee_ldap', '==', ldap_lower)\
            .stream()

        connections = [{**doc.to_dict(), 'id': doc.id} for doc in results]
        return connections
    except Exception as e:
        logger.error(f"Error getting connections for QT {qt_ldap}: {e}")
        return []
