import os
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, List, Optional
from dotenv import load_dotenv
from supabase import create_client, Client

# Import the WhatsApp sender function
from sender import send_whatsapp_message

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Mercado Pago configuration
MP_ACCESS_TOKEN = os.getenv("MERCADOPAGO_ACCESS_TOKEN")
MP_API_BASE_URL = "https://api.mercadopago.com"

class MercadoPagoIntegration:
    def __init__(self, access_token: str = None):
        """
        Initialize the MercadoPago integration with the provided access token.
        If no token is provided, it will use the one from environment variables.
        """
        self.access_token = access_token or MP_ACCESS_TOKEN
        if not self.access_token:
            raise ValueError("MercadoPago access token is required")
        
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    def create_plan(self, plan_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a subscription plan in MercadoPago.
        
        Args:
            plan_data: Dictionary with plan details
                - name: Plan name
                - description: Plan description
                - price: Plan price
                - currency_id: Currency (default: ARS)
                - interval: Billing interval (default: month)
                - frequency: Billing frequency (default: 1)
                - trial_period_days: Trial period in days (optional)
                
        Returns:
            Dictionary with the created plan data
        """
        endpoint = f"{MP_API_BASE_URL}/preapproval_plan"
        
        # Set default values
        plan_data.setdefault("currency_id", "ARS")
        plan_data.setdefault("interval", "month")
        plan_data.setdefault("frequency", 1)
        
        # Format the payload according to MercadoPago API requirements
        payload = {
            "auto_recurring": {
                "frequency": plan_data["frequency"],
                "frequency_type": plan_data["interval"],
                "transaction_amount": float(plan_data["price"]),
                "currency_id": plan_data["currency_id"]
            },
            "back_url": plan_data.get("back_url", "https://tuwebfacil.com/thanks"),
            "reason": plan_data["name"],
            "status": "active"
        }
        
        # Add trial period if specified
        if "trial_period_days" in plan_data and plan_data["trial_period_days"] > 0:
            payload["auto_recurring"]["free_trial"] = {
                "frequency": plan_data["trial_period_days"],
                "frequency_type": "days"
            }
        
        try:
            response = requests.post(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            plan = response.json()
            
            # Store plan in Supabase for reference
            self._store_plan_in_db(plan)
            
            return plan
        except requests.exceptions.RequestException as e:
            print(f"Error creating plan: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}")
            raise
    
    def create_subscription(self, client_id: str, plan_id: str, payer_email: str) -> Dict[str, Any]:
        """
        Create a subscription for a client to a specific plan.
        
        Args:
            client_id: Supabase client ID
            plan_id: MercadoPago plan ID
            payer_email: Email of the payer
            
        Returns:
            Dictionary with the created subscription data
        """
        endpoint = f"{MP_API_BASE_URL}/preapproval"
        
        # Get client data from Supabase
        client_data = self._get_client_data(client_id)
        if not client_data:
            raise ValueError(f"Client with ID {client_id} not found")
        
        # Prepare the payload
        payload = {
            "preapproval_plan_id": plan_id,
            "reason": f"Suscripción a TuWebFacil - {client_data.get('name', 'Cliente')}",
            "external_reference": client_id,
            "payer_email": payer_email,
            "status": "pending",
            "auto_recurring": {
                "currency_id": "ARS",
                "transaction_amount": None,  # Will be taken from the plan
                "frequency": None,  # Will be taken from the plan
                "frequency_type": None  # Will be taken from the plan
            }
        }
        
        try:
            response = requests.post(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            subscription = response.json()
            
            # Store subscription in Supabase
            self._store_subscription_in_db(client_id, subscription)
            
            return subscription
        except requests.exceptions.RequestException as e:
            print(f"Error creating subscription: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}")
            raise
    
    def get_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Get subscription details from MercadoPago.
        
        Args:
            subscription_id: MercadoPago subscription ID
            
        Returns:
            Dictionary with subscription details
        """
        endpoint = f"{MP_API_BASE_URL}/preapproval/{subscription_id}"
        
        try:
            response = requests.get(endpoint, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting subscription: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}")
            raise
    
    def cancel_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Cancel a subscription in MercadoPago.
        
        Args:
            subscription_id: MercadoPago subscription ID
            
        Returns:
            Dictionary with the updated subscription data
        """
        endpoint = f"{MP_API_BASE_URL}/preapproval/{subscription_id}"
        
        payload = {
            "status": "cancelled"
        }
        
        try:
            response = requests.put(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            subscription = response.json()
            
            # Update subscription in Supabase
            self._update_subscription_in_db(subscription_id, {"status": "canceled"})
            
            return subscription
        except requests.exceptions.RequestException as e:
            print(f"Error cancelling subscription: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}")
            raise
    
    def pause_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Pause a subscription in MercadoPago.
        
        Args:
            subscription_id: MercadoPago subscription ID
            
        Returns:
            Dictionary with the updated subscription data
        """
        endpoint = f"{MP_API_BASE_URL}/preapproval/{subscription_id}"
        
        payload = {
            "status": "paused"
        }
        
        try:
            response = requests.put(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            subscription = response.json()
            
            # Update subscription in Supabase
            self._update_subscription_in_db(subscription_id, {"status": "paused"})
            
            return subscription
        except requests.exceptions.RequestException as e:
            print(f"Error pausing subscription: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}")
            raise
    
    def resume_subscription(self, subscription_id: str) -> Dict[str, Any]:
        """
        Resume a paused subscription in MercadoPago.
        
        Args:
            subscription_id: MercadoPago subscription ID
            
        Returns:
            Dictionary with the updated subscription data
        """
        endpoint = f"{MP_API_BASE_URL}/preapproval/{subscription_id}"
        
        payload = {
            "status": "authorized"
        }
        
        try:
            response = requests.put(endpoint, headers=self.headers, json=payload)
            response.raise_for_status()
            subscription = response.json()
            
            # Update subscription in Supabase
            self._update_subscription_in_db(subscription_id, {"status": "active"})
            
            return subscription
        except requests.exceptions.RequestException as e:
            print(f"Error resuming subscription: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}")
            raise
    
    def process_webhook(self, webhook_data: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Process a webhook notification from MercadoPago.
        
        Args:
            webhook_data: Webhook data from MercadoPago
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Extract the notification type and ID
            notification_type = webhook_data.get("type")
            resource_id = webhook_data.get("data", {}).get("id")
            
            if not notification_type or not resource_id:
                return False, "Invalid webhook data"
            
            if notification_type == "preapproval":
                # Handle subscription-related notifications
                return self._handle_subscription_notification(resource_id)
            elif notification_type == "payment":
                # Handle payment-related notifications
                return self._handle_payment_notification(resource_id)
            else:
                return False, f"Unhandled notification type: {notification_type}"
        except Exception as e:
            print(f"Error processing webhook: {e}")
            return False, f"Error: {str(e)}"
    
    def _handle_subscription_notification(self, subscription_id: str) -> Tuple[bool, str]:
        """
        Handle a subscription-related notification.
        
        Args:
            subscription_id: MercadoPago subscription ID
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Get the subscription details
            subscription = self.get_subscription(subscription_id)
            
            # Update the subscription in our database
            status = subscription.get("status", "unknown")
            self._update_subscription_in_db(subscription_id, {"status": status})
            
            # Get the client associated with this subscription
            client_id = subscription.get("external_reference")
            if not client_id:
                return False, "No client ID found in subscription"
            
            client_data = self._get_client_data(client_id)
            if not client_data:
                return False, f"Client with ID {client_id} not found"
            
            # Handle different status changes
            if status == "cancelled":
                # Subscription was cancelled
                self._notify_client_subscription_cancelled(client_data)
            elif status == "paused":
                # Subscription was paused
                self._notify_client_subscription_paused(client_data)
            elif status == "authorized":
                # Subscription was authorized/resumed
                self._notify_client_subscription_active(client_data)
            
            return True, f"Processed subscription notification: {status}"
        except Exception as e:
            print(f"Error handling subscription notification: {e}")
            return False, f"Error: {str(e)}"
    
    def _handle_payment_notification(self, payment_id: str) -> Tuple[bool, str]:
        """
        Handle a payment-related notification.
        
        Args:
            payment_id: MercadoPago payment ID
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Get the payment details
            payment = self._get_payment(payment_id)
            
            # Extract relevant information
            status = payment.get("status", "unknown")
            subscription_id = payment.get("preapproval_id")
            
            if not subscription_id:
                return False, "No subscription ID found in payment"
            
            # Get the subscription details
            subscription = self.get_subscription(subscription_id)
            
            # Get the client associated with this subscription
            client_id = subscription.get("external_reference")
            if not client_id:
                return False, "No client ID found in subscription"
            
            client_data = self._get_client_data(client_id)
            if not client_data:
                return False, f"Client with ID {client_id} not found"
            
            # Store the payment in our database
            self._store_payment_in_db(client_id, subscription_id, payment)
            
            # Handle different payment statuses
            if status == "approved":
                # Payment was successful
                self._handle_successful_payment(client_data, subscription, payment)
            elif status in ["rejected", "cancelled", "refunded"]:
                # Payment failed
                self._handle_failed_payment(client_data, subscription, payment)
            
            return True, f"Processed payment notification: {status}"
        except Exception as e:
            print(f"Error handling payment notification: {e}")
            return False, f"Error: {str(e)}"
    
    def _get_payment(self, payment_id: str) -> Dict[str, Any]:
        """
        Get payment details from MercadoPago.
        
        Args:
            payment_id: MercadoPago payment ID
            
        Returns:
            Dictionary with payment details
        """
        endpoint = f"{MP_API_BASE_URL}/v1/payments/{payment_id}"
        
        try:
            response = requests.get(endpoint, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error getting payment: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response: {e.response.text}")
            raise
    
    def _handle_successful_payment(self, client_data: Dict[str, Any], subscription: Dict[str, Any], payment: Dict[str, Any]) -> None:
        """
        Handle a successful payment.
        
        Args:
            client_data: Client data from Supabase
            subscription: Subscription data from MercadoPago
            payment: Payment data from MercadoPago
        """
        # Update subscription in Supabase
        subscription_id = subscription.get("id")
        
        # Calculate next payment date
        payment_date = datetime.fromisoformat(payment.get("date_created", datetime.utcnow().isoformat()).replace("Z", "+00:00"))
        
        # Determine the interval from the subscription
        interval = subscription.get("auto_recurring", {}).get("frequency_type", "month")
        frequency = subscription.get("auto_recurring", {}).get("frequency", 1)
        
        # Calculate next payment date
        if interval == "month":
            next_payment_date = payment_date + timedelta(days=30 * frequency)
        elif interval == "day":
            next_payment_date = payment_date + timedelta(days=frequency)
        elif interval == "week":
            next_payment_date = payment_date + timedelta(weeks=frequency)
        else:  # Default to monthly
            next_payment_date = payment_date + timedelta(days=30)
        
        # Update subscription in Supabase
        self._update_subscription_in_db(subscription_id, {
            "status": "active",
            "last_payment_date": payment_date.isoformat(),
            "next_payment_date": next_payment_date.isoformat()
        })
        
        # Notify client about successful payment
        self._notify_client_payment_successful(client_data, payment)
    
    def _handle_failed_payment(self, client_data: Dict[str, Any], subscription: Dict[str, Any], payment: Dict[str, Any]) -> None:
        """
        Handle a failed payment.
        
        Args:
            client_data: Client data from Supabase
            subscription: Subscription data from MercadoPago
            payment: Payment data from MercadoPago
        """
        # Update subscription in Supabase
        subscription_id = subscription.get("id")
        self._update_subscription_in_db(subscription_id, {
            "status": "payment_failed"
        })
        
        # Notify client about failed payment
        self._notify_client_payment_failed(client_data, payment)
    
    def _notify_client_payment_successful(self, client_data: Dict[str, Any], payment: Dict[str, Any]) -> None:
        """
        Notify client about a successful payment via WhatsApp.
        
        Args:
            client_data: Client data from Supabase
            payment: Payment data from MercadoPago
        """
        phone = client_data.get("phone")
        if not phone:
            print(f"Cannot notify client: no phone number found")
            return
        
        name = client_data.get("name", "Cliente")
        amount = payment.get("transaction_amount", 0)
        currency = payment.get("currency_id", "ARS")
        
        message = f"""
        ¡Hola {name}! 👋

        Tu pago de {amount} {currency} ha sido procesado con éxito. ✅

        Tu suscripción a TuWebFacil sigue activa y tu sitio web continúa funcionando normalmente.

        Gracias por confiar en nosotros.
        """
        
        send_whatsapp_message(phone, message.strip())
    
    def _notify_client_payment_failed(self, client_data: Dict[str, Any], payment: Dict[str, Any]) -> None:
        """
        Notify client about a failed payment via WhatsApp.
        
        Args:
            client_data: Client data from Supabase
            payment: Payment data from MercadoPago
        """
        phone = client_data.get("phone")
        if not phone:
            print(f"Cannot notify client: no phone number found")
            return
        
        name = client_data.get("name", "Cliente")
        amount = payment.get("transaction_amount", 0)
        currency = payment.get("currency_id", "ARS")
        status = payment.get("status", "rechazado")
        status_detail = payment.get("status_detail", "")
        
        # Get payment link
        payment_link = self._generate_payment_link(client_data, payment)
        
        message = f"""
        ¡Hola {name}! 👋

        Hemos detectado un problema con tu pago de {amount} {currency}. ❌

        Estado: {status}
        Detalle: {status_detail}

        Para mantener tu sitio web activo, por favor actualiza tu método de pago lo antes posible:
        {payment_link}

        Si necesitas ayuda, responde a este mensaje y te asistiremos.
        """
        
        send_whatsapp_message(phone, message.strip())
    
    def _notify_client_subscription_cancelled(self, client_data: Dict[str, Any]) -> None:
        """
        Notify client about a cancelled subscription via WhatsApp.
        
        Args:
            client_data: Client data from Supabase
        """
        phone = client_data.get("phone")
        if not phone:
            print(f"Cannot notify client: no phone number found")
            return
        
        name = client_data.get("name", "Cliente")
        
        message = f"""
        ¡Hola {name}! 👋

        Tu suscripción a TuWebFacil ha sido cancelada. 

        Tu sitio web permanecerá activo hasta el final del período pagado.

        Si deseas reactivar tu suscripción, responde a este mensaje y te ayudaremos.

        Gracias por haber confiado en nosotros.
        """
        
        send_whatsapp_message(phone, message.strip())
    
    def _notify_client_subscription_paused(self, client_data: Dict[str, Any]) -> None:
        """
        Notify client about a paused subscription via WhatsApp.
        
        Args:
            client_data: Client data from Supabase
        """
        phone = client_data.get("phone")
        if not phone:
            print(f"Cannot notify client: no phone number found")
            return
        
        name = client_data.get("name", "Cliente")
        
        message = f"""
        ¡Hola {name}! 👋

        Tu suscripción a TuWebFacil ha sido pausada temporalmente.

        Tu sitio web permanecerá activo hasta el final del período pagado.

        Para reactivar tu suscripción, responde a este mensaje y te ayudaremos.
        """
        
        send_whatsapp_message(phone, message.strip())
    
    def _notify_client_subscription_active(self, client_data: Dict[str, Any]) -> None:
        """
        Notify client about an active subscription via WhatsApp.
        
        Args:
            client_data: Client data from Supabase
        """
        phone = client_data.get("phone")
        if not phone:
            print(f"Cannot notify client: no phone number found")
            return
        
        name = client_data.get("name", "Cliente")
        
        message = f"""
        ¡Hola {name}! 👋

        Tu suscripción a TuWebFacil está activa. ✅

        Tu sitio web está funcionando normalmente y puedes seguir gestionándolo a través de WhatsApp.

        Gracias por confiar en nosotros.
        """
        
        send_whatsapp_message(phone, message.strip())
    
    def _generate_payment_link(self, client_data: Dict[str, Any], payment: Dict[str, Any]) -> str:
        """
        Generate a payment link for the client to update their payment method.
        
        Args:
            client_data: Client data from Supabase
            payment: Payment data from MercadoPago
            
        Returns:
            Payment link URL
        """
        # In a real implementation, this would generate a unique payment link
        # For now, we'll return a placeholder
        return "https://tuwebfacil.com/pagos/actualizar"
    
    def _get_client_data(self, client_id: str) -> Optional[Dict[str, Any]]:
        """
        Get client data from Supabase.
        
        Args:
            client_id: Supabase client ID
            
        Returns:
            Dictionary with client data or None if not found
        """
        try:
            result = supabase.table("clients").select("*").eq("id", client_id).execute()
            if result.data and len(result.data) > 0:
                return result.data[0]
            return None
        except Exception as e:
            print(f"Error getting client data: {e}")
            return None
    
    def _store_plan_in_db(self, plan: Dict[str, Any]) -> None:
        """
        Store a MercadoPago plan in Supabase.
        
        Args:
            plan: Plan data from MercadoPago
        """
        try:
            # Extract relevant plan data
            plan_data = {
                "mercadopago_plan_id": plan.get("id"),
                "name": plan.get("reason"),
                "status": plan.get("status"),
                "price": plan.get("auto_recurring", {}).get("transaction_amount"),
                "currency": plan.get("auto_recurring", {}).get("currency_id"),
                "interval": plan.get("auto_recurring", {}).get("frequency_type"),
                "frequency": plan.get("auto_recurring", {}).get("frequency"),
                "metadata": json.dumps(plan)
            }
            
            # Check if plan already exists
            result = supabase.table("mercadopago_plans").select("*").eq("mercadopago_plan_id", plan.get("id")).execute()
            
            if result.data and len(result.data) > 0:
                # Update existing plan
                supabase.table("mercadopago_plans").update(plan_data).eq("mercadopago_plan_id", plan.get("id")).execute()
            else:
                # Insert new plan
                supabase.table("mercadopago_plans").insert(plan_data).execute()
        except Exception as e:
            print(f"Error storing plan in DB: {e}")
    
    def _store_subscription_in_db(self, client_id: str, subscription: Dict[str, Any]) -> None:
        """
        Store a MercadoPago subscription in Supabase.
        
        Args:
            client_id: Supabase client ID
            subscription: Subscription data from MercadoPago
        """
        try:
            # Extract relevant subscription data
            subscription_data = {
                "client_id": client_id,
                "mercadopago_subscription_id": subscription.get("id"),
                "plan_type": subscription.get("reason"),
                "status": subscription.get("status"),
                "start_date": datetime.utcnow().isoformat(),
                "price": subscription.get("auto_recurring", {}).get("transaction_amount"),
                "auto_renew": True,
                "mercadopago_subscription_id": subscription.get("id"),
                "metadata": json.dumps(subscription)
            }
            
            # Check if subscription already exists
            result = supabase.table("subscriptions").select("*").eq("mercadopago_subscription_id", subscription.get("id")).execute()
            
            if result.data and len(result.data) > 0:
                # Update existing subscription
                supabase.table("subscriptions").update(subscription_data).eq("mercadopago_subscription_id", subscription.get("id")).execute()
            else:
                # Insert new subscription
                supabase.table("subscriptions").insert(subscription_data).execute()
        except Exception as e:
            print(f"Error storing subscription in DB: {e}")
    
    def _update_subscription_in_db(self, subscription_id: str, update_data: Dict[str, Any]) -> None:
        """
        Update a subscription in Supabase.
        
        Args:
            subscription_id: MercadoPago subscription ID
            update_data: Data to update
        """
        try:
            supabase.table("subscriptions").update(update_data).eq("mercadopago_subscription_id", subscription_id).execute()
        except Exception as e:
            print(f"Error updating subscription in DB: {e}")
    
    def _store_payment_in_db(self, client_id: str, subscription_id: str, payment: Dict[str, Any]) -> None:
        """
        Store a payment in Supabase.
        
        Args:
            client_id: Supabase client ID
            subscription_id: MercadoPago subscription ID
            payment: Payment data from MercadoPago
        """
        try:
            # Get subscription ID from Supabase
            result = supabase.table("subscriptions").select("id").eq("mercadopago_subscription_id", subscription_id).execute()
            
            if not result.data or len(result.data) == 0:
                print(f"Subscription with MercadoPago ID {subscription_id} not found in DB")
                return
            
            supabase_subscription_id = result.data[0]["id"]
            
            # Extract relevant payment data
            payment_data = {
                "client_id": client_id,
                "subscription_id": supabase_subscription_id,
                "amount": payment.get("transaction_amount"),
                "currency": payment.get("currency_id"),
                "status": payment.get("status"),
                "payment_method": payment.get("payment_method_id"),
                "mercadopago_payment_id": payment.get("id"),
                "payment_date": payment.get("date_approved") or payment.get("date_created"),
                "metadata": json.dumps(payment)
            }
            
            # Check if payment already exists
            result = supabase.table("payments").select("*").eq("mercadopago_payment_id", payment.get("id")).execute()
            
            if result.data and len(result.data) > 0:
                # Update existing payment
                supabase.table("payments").update(payment_data).eq("mercadopago_payment_id", payment.get("id")).execute()
            else:
                # Insert new payment
                supabase.table("payments").insert(payment_data).execute()
        except Exception as e:
            print(f"Error storing payment in DB: {e}")


# Flask route handler for MercadoPago webhooks
def handle_mercadopago_webhook(request_data):
    """
    Handle MercadoPago webhook notifications.
    
    Args:
        request_data: Webhook data from MercadoPago
        
    Returns:
        Tuple of (success, message)
    """
    try:
        mp = MercadoPagoIntegration()
        return mp.process_webhook(request_data)
    except Exception as e:
        print(f"Error handling MercadoPago webhook: {e}")
        return False, f"Error: {str(e)}"


# Helper functions for creating subscriptions

def create_subscription_for_client(client_id: str, plan_type: str, email: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Create a subscription for a client.
    
    Args:
        client_id: Supabase client ID
        plan_type: Type of plan (basic, premium, etc.)
        email: Client's email address
        
    Returns:
        Tuple of (success, message, subscription_data)
    """
    try:
        # Get plan ID for the specified plan type
        result = supabase.table("mercadopago_plans").select("*").eq("name", plan_type).eq("status", "active").execute()
        
        if not result.data or len(result.data) == 0:
            return False, f"No active plan found for type: {plan_type}", None
        
        plan_id = result.data[0]["mercadopago_plan_id"]
        
        # Create subscription
        mp = MercadoPagoIntegration()
        subscription = mp.create_subscription(client_id, plan_id, email)
        
        return True, "Subscription created successfully", subscription
    except Exception as e:
        print(f"Error creating subscription for client: {e}")
        return False, f"Error: {str(e)}", None


def get_payment_link_for_subscription(subscription_id: str) -> Tuple[bool, str, Optional[str]]:
    """
    Get the payment link for a subscription.
    
    Args:
        subscription_id: MercadoPago subscription ID
        
    Returns:
        Tuple of (success, message, payment_link)
    """
    try:
        mp = MercadoPagoIntegration()
        subscription = mp.get_subscription(subscription_id)
        
        if "init_point" in subscription:
            return True, "Payment link retrieved successfully", subscription["init_point"]
        else:
            return False, "No payment link found in subscription", None
    except Exception as e:
        print(f"Error getting payment link: {e}")
        return False, f"Error: {str(e)}", None


# Example usage
if __name__ == "__main__":
    # This is just for testing purposes
    # Create a plan
    mp = MercadoPagoIntegration()
    
    plan_data = {
        "name": "Plan Básico",
        "description": "Plan básico de TuWebFacil",
        "price": 1999.99,
        "trial_period_days": 7
    }
    
    try:
        plan = mp.create_plan(plan_data)
        print(f"Plan created: {plan['id']}")
        
        # You would then create a subscription for a client
        # subscription = mp.create_subscription("client_id", plan["id"], "client@example.com")
        # print(f"Subscription created: {subscription['id']}")
    except Exception as e:
        print(f"Error in example: {e}")