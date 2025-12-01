"""Salesforce function implementations"""
import json

# In-memory mock of Salesforce objects
# Structure: {object_type: [{id: str, ...fields}]}
_mock_salesforce = {
    "Account": [
        {"Id": "001xx000003DGb0AAG", "Name": "Acme Corporation", "Industry": "Technology", "AnnualRevenue": 5000000},
        {"Id": "001xx000003DGb1AAG", "Name": "Global Industries", "Industry": "Manufacturing", "AnnualRevenue": 12000000},
        {"Id": "001xx000003DGb2AAG", "Name": "Tech Solutions", "Industry": "Technology", "AnnualRevenue": 3000000},
    ],
    "Contact": [
        {"Id": "003xx000004TmiQAAS", "FirstName": "John", "LastName": "Doe", "Email": "john.doe@acme.com", "AccountId": "001xx000003DGb0AAG"},
        {"Id": "003xx000004TmiRAAS", "FirstName": "Jane", "LastName": "Smith", "Email": "jane.smith@global.com", "AccountId": "001xx000003DGb1AAG"},
        {"Id": "003xx000004TmiSAAS", "FirstName": "Bob", "LastName": "Johnson", "Email": "bob.j@techsol.com", "AccountId": "001xx000003DGb2AAG"},
    ],
    "Opportunity": [
        {"Id": "006xx000001xYZ0AAM", "Name": "Big Deal", "Amount": 500000, "StageName": "Prospecting", "AccountId": "001xx000003DGb0AAG"},
        {"Id": "006xx000001xYZ1AAM", "Name": "Medium Deal", "Amount": 250000, "StageName": "Negotiation", "AccountId": "001xx000003DGb1AAG"},
    ],
    "Lead": [
        {"Id": "00Qxx000001aBcDEAM", "FirstName": "Alice", "LastName": "Williams", "Company": "New Startup", "Email": "alice@newstartup.com", "Status": "Open"},
        {"Id": "00Qxx000001aBcEEAM", "FirstName": "Charlie", "LastName": "Brown", "Company": "Another Co", "Email": "charlie@another.com", "Status": "Contacted"},
    ]
}

_id_counter = 1000

def salesforce_query(query: str) -> str:
    """Execute a SOQL query in Salesforce
    
    Supports basic SOQL syntax:
    - SELECT * FROM ObjectType
    - SELECT field1, field2 FROM ObjectType
    - SELECT * FROM ObjectType WHERE field = 'value'
    - SELECT * FROM ObjectType WHERE field = 'value' LIMIT n
    """
    query = query.strip()
    
    # Simple SOQL parser (very basic)
    if "FROM" not in query.upper():
        return json.dumps({"error": "Invalid SOQL query"})
    
    # Extract LIMIT clause if present
    limit = None
    if "LIMIT" in query.upper():
        limit_parts = query.upper().split("LIMIT")
        if len(limit_parts) == 2:
            try:
                limit = int(limit_parts[1].strip().split()[0])
                # Remove LIMIT clause from query for further processing
                query = query[:query.upper().index("LIMIT")].strip()
            except (ValueError, IndexError):
                pass
    
    # Extract object type
    parts = query.upper().split("FROM")
    if len(parts) < 2:
        return json.dumps({"error": "Invalid SOQL query"})
    
    object_part = parts[1].strip().split()[0]
    
    # Find the actual object type (case-insensitive)
    object_type = None
    for obj in _mock_salesforce.keys():
        if obj.upper() == object_part.upper():
            object_type = obj
            break
    
    if not object_type or object_type not in _mock_salesforce:
        return json.dumps({"error": f"Object type '{object_part}' not found"})
    
    records = _mock_salesforce[object_type].copy()
    
    # Handle WHERE clause (very basic)
    if "WHERE" in query.upper():
        where_clause = query.split("WHERE", 1)[1].strip()
        # Simple equality check: field = 'value' or field = value
        if "=" in where_clause:
            field, value = where_clause.split("=", 1)
            field = field.strip()
            value = value.strip().strip("'\"")
            
            records = [r for r in records if str(r.get(field, "")) == value]
    
    # Apply LIMIT if specified
    if limit is not None and limit > 0:
        records = records[:limit]
    
    return json.dumps({
        "totalSize": len(records),
        "done": True,
        "records": records
    })


def salesforce_create(object_type: str, data: dict) -> str:
    """Create a new record in Salesforce"""
    global _id_counter
    
    # Initialize object type if it doesn't exist
    if object_type not in _mock_salesforce:
        _mock_salesforce[object_type] = []
    
    # Generate a new ID
    _id_counter += 1
    record_id = f"{_id_counter:015d}AAA"
    
    # Create the record
    record = {"Id": record_id, **data}
    _mock_salesforce[object_type].append(record)
    
    return json.dumps({
        "id": record_id,
        "success": True,
        "errors": []
    })

