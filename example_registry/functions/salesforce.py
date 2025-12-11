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
        {"Id": "006xx000001xYZ0AAM", "Name": "Big Deal", "Amount": 500000, "StageName": "Prospecting", "AccountId": "001xx000003DGb0AAG", "IsWon": False, "CloseDate": "2024-12-15"},
        {"Id": "006xx000001xYZ1AAM", "Name": "Medium Deal", "Amount": 250000, "StageName": "Negotiation", "AccountId": "001xx000003DGb1AAG", "IsWon": False, "CloseDate": "2024-11-30"},
        {"Id": "006xx000001xYZ2AAM", "Name": "GreenLeaf Software - Gold Membership", "Amount": 50000, "StageName": "Closed Won", "AccountId": "001xx000003DGb0AAG", "IsWon": True, "CloseDate": "2024-09-15"},
        {"Id": "006xx000001xYZ3AAM", "Name": "GreenLeaf Software - Support Contract", "Amount": 25000, "StageName": "Closed Won", "AccountId": "001xx000003DGb0AAG", "IsWon": True, "CloseDate": "2024-10-20"},
    ],
    "Lead": [
        {"Id": "00Qxx000001aBcDEAM", "FirstName": "Alice", "LastName": "Williams", "Company": "New Startup", "Email": "alice@newstartup.com", "Status": "Open"},
        {"Id": "00Qxx000001aBcEEAM", "FirstName": "Charlie", "LastName": "Brown", "Company": "Another Co", "Email": "charlie@another.com", "Status": "Contacted"},
    ]
}

_id_counter = 1000

def salesforce_query(query: str) -> str:
    """Execute a SOQL query in Salesforce.
    
    Args:
        query: SOQL query string. Supports:
               - SELECT * FROM ObjectType
               - SELECT field1, field2 FROM ObjectType  
               - WHERE field = 'value' AND field2 = 'value2'
               - WHERE field LIKE '%text%' (supports %, %text, text%)
               - WHERE field = true/false (boolean values)
               - ORDER BY field ASC/DESC
               - LIMIT n
               Note: Subqueries in parentheses are stripped (main query only)
    
    Returns:
        JSON string with success status, totalSize, done flag, and records list.
        Each record is a dict with the requested fields and values
    """
    query = query.strip()
    
    # Simple SOQL parser (very basic)
    if "FROM" not in query.upper():
        return json.dumps({"success": False, "error": "Invalid SOQL query"})
    
    # This handles queries like: SELECT ... (SELECT ... FROM Related) FROM Main
    clean_query = ""
    paren_depth = 0
    for char in query:
        if char == '(':
            paren_depth += 1
        elif char == ')':
            paren_depth -= 1
        elif paren_depth == 0:
            clean_query += char
    
    query = clean_query.strip()
    
    # Extract LIMIT clause first (from original query)
    limit = None
    if "LIMIT" in query.upper():
        limit_index = query.upper().find("LIMIT")
        limit_text = query[limit_index + 5:].strip().split()[0]
        try:
            limit = int(limit_text)
        except (ValueError, IndexError):
            pass
    
    # Extract ORDER BY clause if present (before removing it)
    order_field = None
    order_dir = "ASC"
    if "ORDER BY" in query.upper():
        order_by_index = query.upper().find("ORDER BY")
        # Get everything after ORDER BY up to LIMIT (if present) or end
        order_end = len(query)
        if "LIMIT" in query.upper():
            order_end = query.upper().find("LIMIT")
        order_clause = query[order_by_index + 8:order_end].strip()
        
        # Extract field and direction
        order_parts = order_clause.split()
        if order_parts:
            order_field = order_parts[0].strip()
            if len(order_parts) > 1 and order_parts[1].upper() in ("ASC", "DESC"):
                order_dir = order_parts[1].upper()
        
        # Remove ORDER BY (and everything after) from query
        query = query[:order_by_index].strip()
    elif "LIMIT" in query.upper():
        # If no ORDER BY but there's LIMIT, remove it
        limit_index = query.upper().find("LIMIT")
        query = query[:limit_index].strip()
    
    # Extract object type from the main FROM clause
    # Find all FROM occurrences and use the last one (main query)
    from_index = query.upper().rfind("FROM")
    if from_index == -1:
        return json.dumps({"success": False, "error": "Invalid SOQL query"})
    
    after_from = query[from_index + 4:].strip()
    object_part = after_from.split()[0] if after_from.split() else ""
    
    # Find the actual object type (case-insensitive)
    object_type = None
    for obj in _mock_salesforce.keys():
        if obj.upper() == object_part.upper():
            object_type = obj
            break
    
    if not object_type or object_type not in _mock_salesforce:
        return json.dumps({"success": False, "error": f"Object type '{object_part}' not found"})
    
    records = _mock_salesforce[object_type].copy()
    
    # Handle WHERE clause (basic support for = and LIKE with AND)
    if "WHERE" in query.upper():
        where_clause = query.split("WHERE", 1)[1].strip()
        
        # Split by AND to handle multiple conditions
        conditions = [c.strip() for c in where_clause.upper().split(" AND ")]
        original_conditions = [c.strip() for c in where_clause.split(" AND ")]
        
        for i, condition in enumerate(conditions):
            original = original_conditions[i]
            
            # Handle LIKE operator
            if " LIKE " in condition:
                parts = original.split(" LIKE ", 1)
                field = parts[0].strip()
                pattern = parts[1].strip().strip("'\"")
                # Simple LIKE: %text% means contains
                if pattern.startswith("%") and pattern.endswith("%"):
                    search_text = pattern.strip("%")
                    records = [r for r in records if search_text.lower() in str(r.get(field, "")).lower()]
                elif pattern.startswith("%"):
                    search_text = pattern.strip("%")
                    records = [r for r in records if str(r.get(field, "")).lower().endswith(search_text.lower())]
                elif pattern.endswith("%"):
                    search_text = pattern.strip("%")
                    records = [r for r in records if str(r.get(field, "")).lower().startswith(search_text.lower())]
                else:
                    records = [r for r in records if str(r.get(field, "")).lower() == pattern.lower()]
            
            # Handle = operator
            elif "=" in condition:
                parts = original.split("=", 1)
                field = parts[0].strip()
                value = parts[1].strip().strip("'\"")
                
                # Handle boolean values
                if value.lower() in ("true", "false"):
                    value_bool = value.lower() == "true"
                    records = [r for r in records if r.get(field) == value_bool]
                else:
                    records = [r for r in records if str(r.get(field, "")) == value]
    
    # Apply ORDER BY if specified
    if order_field:
        try:
            records = sorted(
                records,
                key=lambda r: r.get(order_field, ""),
                reverse=(order_dir == "DESC")
            )
        except Exception:
            # If sorting fails, just continue without ordering
            pass
    
    # Apply LIMIT if specified
    if limit is not None and limit > 0:
        records = records[:limit]
    
    return json.dumps({
        "success": True,
        "totalSize": len(records),
        "done": True,
        "records": records
    })


def salesforce_describe_object(object_type: str) -> str:
    """Get schema/metadata for a Salesforce object
    
    Returns field names, types, and whether they're required.
    
    Available object types in this mock:
    - Account: Company/organization records
    - Contact: Individual person records
    - Opportunity: Sales opportunity records
    - Lead: Potential customer records
    
    Args:
        object_type: The Salesforce object type to describe
    
    Returns:
        JSON with object schema including fields and their types
    """
    if object_type not in _mock_salesforce:
        return json.dumps({
            "success": False,
            "error": f"Object type '{object_type}' not found. Available: {', '.join(_mock_salesforce.keys())}"
        })
    
    # Get sample record to infer schema
    records = _mock_salesforce[object_type]
    if not records:
        return json.dumps({
            "success": True,
            "object": object_type,
            "fields": [],
            "message": "No records exist to infer schema"
        })
    
    # Infer schema from sample records
    sample = records[0]
    fields = []
    
    for field_name, value in sample.items():
        field_type = "string"  # default
        if isinstance(value, bool):
            field_type = "boolean"
        elif isinstance(value, int):
            field_type = "number"
        elif isinstance(value, float):
            field_type = "currency"
        elif field_name.endswith("Id"):
            field_type = "reference"
        elif field_name.endswith("Date"):
            field_type = "date"
        
        fields.append({
            "name": field_name,
            "type": field_type,
            "required": field_name == "Id"  # Only Id is always present
        })
    
    return json.dumps({
        "success": True,
        "object": object_type,
        "fields": fields,
        "record_count": len(records)
    })


def salesforce_list_objects() -> str:
    """List all available Salesforce object types in this mock.
    
    Returns:
        JSON string with success status, objects list (each with name, label, and description),
        and total count. Helps agents discover which objects are available for querying
    """
    return json.dumps({
        "success": True,
        "objects": [
            {"name": "Account", "label": "Account", "description": "Company/organization records"},
            {"name": "Contact", "label": "Contact", "description": "Individual person records"},
            {"name": "Opportunity", "label": "Opportunity", "description": "Sales opportunity records"},
            {"name": "Lead", "label": "Lead", "description": "Potential customer records"}
        ],
        "total": len(_mock_salesforce)
    })


def salesforce_create(object_type: str, data: dict) -> str:
    """Create a new record in Salesforce.
    
    Args:
        object_type: The Salesforce object type (e.g., 'Account', 'Contact', 'Opportunity', 'Lead')
        data: Dictionary of field names and values for the new record.
              Example: {"FirstName": "John", "LastName": "Doe", "Email": "john@example.com"}
    
    Returns:
        JSON string with id (auto-generated), success status, and errors list (empty on success)
    """
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

