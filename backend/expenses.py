
import json
import os
import boto3
from botocore.exceptions import ClientError


dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
table = dynamodb.Table("SpendlyExpenses")


def create_expense(data):
    import uuid
    from datetime import datetime

    
    if not isinstance(data, dict):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Request body must be a JSON object"})
        }

    required_fields = ["amount", "category", "date"]
    
    for field in required_fields:
        if field not in data or data[field] in (None, ""):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": f"Missing required field: {field}"})
            }
    try:
        datetime.strptime(data["date"], "%Y-%m-%d")
    except (ValueError, TypeError):
        return {
            "statusCode": 400,
            "headers": {
                "Content-Type": "application/json"
            },
            "body": json.dumps({
                "error": "Date must be in YYYY-MM-DD format"
            })
        }
    try:
        amount = float(data["amount"])
        if amount <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Amount must be a positive number"})
        }


    expense = {
        "expenseId": str(uuid.uuid4()),
        "amount": amount,
        "category": data["category"],
        "date": data["date"],
        "description": data.get("description", ""),
        "merchant": data.get("merchant", ""),
        "createdAt": datetime.utcnow().isoformat()
    }

    table.put_item(Item=expense)

    return {
        "statusCode": 201,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(expense)
    }


def get_expenses():
    response = table.scan()

    expenses = response.get("Items", [])

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(expenses)
    }

def update_expense(expense_id, data):
    allowed_fields = [
        "amount",
        "category",
        "date",
        "description",
        "merchant"
    ]

    updates = {
        key: value
        for key, value in data.items()
        if key in allowed_fields
    }

    if not updates:
        return {
            "statusCode": 400,
            "body": json.dumps({
                "error": "No valid fields provided to update"
            })
        }

    if "amount" in updates:
        try:
            updates["amount"] = float(updates["amount"])
            if updates["amount"] <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Amount must be a positive number"
                })
            }

    update_expression = "SET " + ", ".join(
        f"#{key} = :{key}" for key in updates
    )

    
    try:
        response = table.update_item(
            Key={"expenseId": expense_id},
            UpdateExpression=update_expression,
            ExpressionAttributeNames={
                f"#{key}": key for key in updates
            },
            ExpressionAttributeValues={
                f":{key}": value for key, value in updates.items()
            },
            ConditionExpression="attribute_exists(expenseId)",
            ReturnValues="ALL_NEW"
        )
    except ClientError as error:
        error_code = error.response["Error"]["Code"]

        if error_code == "ConditionalCheckFailedException":
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "Expense not found"
                })
            }

        raise

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(response["Attributes"])
    }


    try:
        response = table.delete_item(
            Key={"expenseId": expense_id},
            ConditionExpression="attribute_exists(expenseId)"
        )
    except ClientError as error:
        error_code = error.response["Error"]["Code"]

        if error_code == "ConditionalCheckFailedException":
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "Expense not found"
                })
            }

        raise
    
def delete_expense(expense_id):
    try:
        table.delete_item(
            Key={"expenseId": expense_id},
            ConditionExpression="attribute_exists(expenseId)"
        )
    except ClientError as error:
        error_code = error.response["Error"]["Code"]

        if error_code == "ConditionalCheckFailedException":
            return {
                "statusCode": 404,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps({
                    "error": "Expense not found"
                })
            }

        raise

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({
            "message": "Expense deleted successfully",
            "expenseId": expense_id
        })
    }


def lambda_handler(event, context):
    try:
        method = event.get("httpMethod", "")
        path = event.get("path", "").rstrip("/")
        path_parameters = event.get("pathParameters") or {}
        expense_id = path_parameters.get("expenseId")

        if method == "POST" and path.endswith("/expenses"):
            body = event.get("body") or "{}"
            data = json.loads(body) if isinstance(body, str) else body
            return create_expense(data)

        elif method == "GET" and path.endswith("/expenses"):
            return get_expenses()

        elif method == "PUT" and expense_id:
            body = event.get("body") or "{}"
            data = json.loads(body) if isinstance(body, str) else body
            return update_expense(expense_id, data)

        elif method == "DELETE" and expense_id:
            return delete_expense(expense_id)

        return {
            "statusCode": 404,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Route not found"})
        }

    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Invalid JSON request body"})
        }

    except Exception as error:
        print(f"Backend error: {error}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Internal server error"})
        }
