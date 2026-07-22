import os
import json
import requests
from datetime import datetime
from typing import Dict, Any, Optional, Tuple
from dotenv import load_dotenv
import google.generativeai as genai
from supabase import create_client, Client

# Import from other modules
from sender import send_whatsapp_message
from mercadopago_integration import MercadoPagoIntegration, create_subscription_for_client

# Load environment variables
load_dotenv()

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# Configure Gemini AI
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

class ClientProvisioner:
    def __init__(self):
        """
        Initialize the Client Provisioner with necessary configurations.
        """
        # Detect available Gemini model
        try:
            models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
            self.model_name = "models/gemini-2.5-flash" if "models/gemini-2.5-flash" in models else models[0]
            self.model = genai.GenerativeModel(self.model_name)
            print(f"Using Gemini model: {self.model_name}")
        except Exception as e:
            print(f"Error initializing Gemini model: {e}")
            raise
        
        # Initialize MercadoPago integration
        self.mp_integration = MercadoPagoIntegration()
    
    def provision_client(self, phone: str, name: str, instagram_handle: str, email: Optional[str] = None) -> Dict[str, Any]:
        """
        Provision a new client based on their Instagram profile.
        
        Args:
            phone: Client's WhatsApp phone number
            name: Client's name
            instagram_handle: Client's Instagram handle
            email: Client's email address (optional)
            
        Returns:
            Dictionary with provisioning results
        """
        try:
            # 1. Create or update client in database
            client_id = self._create_or_update_client(phone, name, instagram_handle, email)
            
            # 2. Analyze Instagram profile
            instagram_data = self._analyze_instagram_profile(instagram_handle)
            
            # 3. Determine business type
            business_type = self._determine_business_type(instagram_data)
            
            # 4. Update client with business type
            self._update_client_business_type(client_id, business_type)
            
            # 5. Generate website content
            website_content = self._generate_website_content(instagram_data, business_type)
            
            # 6. Create website
            website_id = self._create_website(client_id, website_content)
            
            # 7. Send welcome message with website preview
            self._send_welcome_message(phone, name, website_id)
            
            # 8. Return provisioning results
            return {
                "client_id": client_id,
                "website_id": website_id,
                "business_type": business_type,
                "instagram_data": instagram_data,
                "provisioned_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            print(f"Error provisioning client: {e}")
            # Send error message to client
            error_message = f"Lo sentimos, {name}. Hemos tenido un problema al configurar tu sitio web. Nuestro equipo está trabajando para solucionarlo y te contactaremos pronto."
            send_whatsapp_message(phone, error_message)
            raise
    
    def setup_subscription(self, client_id: str, plan_type: str, email: str) -> Dict[str, Any]:
        """
        Set up a subscription for a client.
        
        Args:
            client_id: Client ID
            plan_type: Subscription plan type (basic, premium, etc.)
            email: Client's email address
            
        Returns:
            Dictionary with subscription results
        """
        try:
            # Create subscription
            success, message, subscription = create_subscription_for_client(client_id, plan_type, email)
            
            if not success:
                raise ValueError(f"Failed to create subscription: {message}")
            
            # Get client data
            client_data = self._get_client_data(client_id)
            
            # Send subscription confirmation message
            self._send_subscription_message(client_data.get("phone"), client_data.get("name"), subscription)
            
            return {
                "client_id": client_id,
                "subscription_id": subscription.get("id"),
                "plan_type": plan_type,
                "status": subscription.get("status"),
                "created_at": datetime.utcnow().isoformat()
            }
        except Exception as e:
            print(f"Error setting up subscription: {e}")
            raise
    
    def _create_or_update_client(self, phone: str, name: str, instagram_handle: str, email: Optional[str] = None) -> str:
        """
        Create or update a client in the database.
        
        Args:
            phone: Client's WhatsApp phone number
            name: Client's name
            instagram_handle: Client's Instagram handle
            email: Client's email address (optional)
            
        Returns:
            Client ID
        """
        try:
            # Check if client already exists
            result = supabase.table("clients").select("*").eq("phone", phone).execute()
            
            client_data = {
                "phone": phone,
                "name": name,
                "instagram_handle": instagram_handle,
                "status": "lead"
            }
            
            if email:
                client_data["email"] = email
            
            if result.data and len(result.data) > 0:
                # Update existing client
                client_id = result.data[0]["id"]
                supabase.table("clients").update(client_data).eq("id", client_id).execute()
            else:
                # Create new client
                result = supabase.table("clients").insert(client_data).execute()
                client_id = result.data[0]["id"]
            
            return client_id
        except Exception as e:
            print(f"Error creating or updating client: {e}")
            raise
    
    def _analyze_instagram_profile(self, instagram_handle: str) -> Dict[str, Any]:
        """
        Analyze an Instagram profile to extract business information.
        
        Args:
            instagram_handle: Instagram handle to analyze
            
        Returns:
            Dictionary with Instagram profile analysis
        """
        try:
            # In a real implementation, this would use the Instagram Graph API
            # For now, we'll use Gemini AI to generate mock data
            
            prompt = f"""
            Analyze this Instagram handle: @{instagram_handle}
            
            Generate a detailed analysis of what this business might be about.
            
            Format your response as a JSON object with the following structure:
            {{
                "business_name": "Name of the business",
                "business_type": "Type of business (restaurant, retail, fitness, beauty, etc.)",
                "description": "Brief description of the business",
                "products_services": ["Product/Service 1", "Product/Service 2"],
                "target_audience": ["Audience 1", "Audience 2"],
                "tone_and_style": "Description of the brand's tone and style",
                "color_scheme": ["#hexcolor1", "#hexcolor2"],
                "key_selling_points": ["Selling Point 1", "Selling Point 2"]
            }}
            """
            
            response = self.model.generate_content(prompt)
            
            # Parse the response
            instagram_data = json.loads(response.text)
            
            # Add metadata
            instagram_data["analyzed_at"] = datetime.utcnow().isoformat()
            instagram_data["instagram_handle"] = instagram_handle
            
            return instagram_data
        except Exception as e:
            print(f"Error analyzing Instagram profile: {e}")
            # Return a simple fallback analysis
            return {
                "business_name": instagram_handle,
                "business_type": "general",
                "description": "Business with Instagram presence",
                "products_services": ["Products", "Services"],
                "target_audience": ["General audience"],
                "tone_and_style": "Professional",
                "color_scheme": ["#4a90e2", "#ffffff"],
                "key_selling_points": ["Quality service", "Professional approach"],
                "analyzed_at": datetime.utcnow().isoformat(),
                "instagram_handle": instagram_handle,
                "error": str(e)
            }
    
    def _determine_business_type(self, instagram_data: Dict[str, Any]) -> str:
        """
        Determine the business type based on Instagram data.
        
        Args:
            instagram_data: Instagram profile analysis
            
        Returns:
            Business type
        """
        # Extract business type from Instagram data
        business_type = instagram_data.get("business_type", "").lower()
        
        # Map to standard business types
        business_type_mapping = {
            "restaurant": "restaurant",
            "cafe": "restaurant",
            "food": "restaurant",
            "retail": "retail",
            "shop": "retail",
            "store": "retail",
            "fitness": "fitness",
            "gym": "fitness",
            "beauty": "beauty",
            "salon": "beauty",
            "web": "web_development",
            "development": "web_development",
            "design": "web_development"
        }
        
        # Find matching business type
        for key, value in business_type_mapping.items():
            if key in business_type:
                return value
        
        # Default to general
        return "general"
    
    def _update_client_business_type(self, client_id: str, business_type: str) -> None:
        """
        Update a client's business type in the database.
        
        Args:
            client_id: Client ID
            business_type: Business type
        """
        try:
            supabase.table("clients").update({"business_type": business_type}).eq("id", client_id).execute()
        except Exception as e:
            print(f"Error updating client business type: {e}")
            raise
    
    def _generate_website_content(self, instagram_data: Dict[str, Any], business_type: str) -> Dict[str, Any]:
        """
        Generate website content based on Instagram data and business type.
        
        Args:
            instagram_data: Instagram profile analysis
            business_type: Business type
            
        Returns:
            Dictionary with website content
        """
        try:
            # Prepare the prompt
            prompt = f"""
            Generate website content for a {business_type} business based on this Instagram profile analysis:
            
            {json.dumps(instagram_data, indent=2)}
            
            Format your response as a JSON object with the following structure:
            {{
                "header": {{
                    "logo": "Description of logo",
                    "title": "Business name",
                    "tagline": "Catchy tagline",
                    "menu": [
                        {{"label": "Home", "url": "/"}},
                        {{"label": "Services", "url": "/services"}},
                        {{"label": "Gallery", "url": "/gallery"}},
                        {{"label": "Contact", "url": "/contact"}}
                    ]
                }},
                "hero": {{
                    "title": "Main headline",
                    "subtitle": "Supporting text",
                    "background_image": "Description of background image",
                    "cta_button": {{
                        "text": "Call to action text",
                        "url": "/contact"
                    }}
                }},
                "sections": [
                    {{
                        "type": "about",
                        "title": "About Us",
                        "content": "Detailed about us text",
                        "image": "Description of image"
                    }},
                    {{
                        "type": "services",
                        "title": "Our Services",
                        "items": [
                            {{
                                "title": "Service 1",
                                "description": "Description of service 1",
                                "icon": "Icon name",
                                "image": "Description of image"
                            }}
                        ]
                    }},
                    {{
                        "type": "gallery",
                        "title": "Our Work",
                        "images": [
                            {{
                                "url": "Description of image 1",
                                "caption": "Caption 1",
                                "alt": "Alt text 1"
                            }}
                        ]
                    }}
                ],
                "footer": {{
                    "copyright": "Copyright text",
                    "social_links": [
                        {{"platform": "instagram", "url": "Instagram URL"}}
                    ],
                    "contact_info": {{
                        "email": "contact@example.com",
                        "phone": "+1234567890",
                        "address": "Business address"
                    }}
                }},
                "seo": {{
                    "title": "SEO title",
                    "description": "SEO description",
                    "keywords": ["keyword1", "keyword2"]
                }}
            }}
            """
            
            response = self.model.generate_content(prompt)
            
            # Parse the response
            website_content = json.loads(response.text)
            
            # Add metadata
            website_content["generated_at"] = datetime.utcnow().isoformat()
            website_content["business_type"] = business_type
            
            return website_content
        except Exception as e:
            print(f"Error generating website content: {e}")
            # Return a simple fallback content
            business_name = instagram_data.get("business_name", "Business Name")
            return {
                "header": {
                    "logo": "Business logo",
                    "title": business_name,
                    "tagline": "Professional services",
                    "menu": [
                        {"label": "Home", "url": "/"},
                        {"label": "Services", "url": "/services"},
                        {"label": "Contact", "url": "/contact"}
                    ]
                },
                "hero": {
                    "title": f"Welcome to {business_name}",
                    "subtitle": "We provide professional services",
                    "background_image": "Professional business image",
                    "cta_button": {
                        "text": "Contact Us",
                        "url": "/contact"
                    }
                },
                "sections": [
                    {
                        "type": "about",
                        "title": "About Us",
                        "content": f"{business_name} is a professional business dedicated to providing high-quality services to our clients.",
                        "image": "Team image"
                    },
                    {
                        "type": "services",
                        "title": "Our Services",
                        "items": [
                            {
                                "title": "Professional Service",
                                "description": "We provide high-quality professional services.",
                                "icon": "service-icon",
                                "image": "Service image"
                            }
                        ]
                    }
                ],
                "footer": {
                    "copyright": f"© {datetime.now().year} {business_name}. All rights reserved.",
                    "social_links": [
                        {"platform": "instagram", "url": f"https://instagram.com/{instagram_data.get('instagram_handle')}"}
                    ],
                    "contact_info": {
                        "email": "contact@example.com",
                        "phone": "+1234567890",
                        "address": "Business address"
                    }
                },
                "seo": {
                    "title": f"{business_name} | Professional Services",
                    "description": f"{business_name} provides high-quality professional services.",
                    "keywords": ["professional", "services", business_type]
                },
                "generated_at": datetime.utcnow().isoformat(),
                "business_type": business_type,
                "error": str(e)
            }
    
    def _create_website(self, client_id: str, website_content: Dict[str, Any]) -> str:
        """
        Create a website for a client.
        
        Args:
            client_id: Client ID
            website_content: Website content
            
        Returns:
            Website ID
        """
        try:
            # Get client data
            client_data = self._get_client_data(client_id)
            
            # Generate subdomain from business name
            business_name = website_content.get("header", {}).get("title", "business")
            subdomain = self._generate_subdomain(business_name)
            
            # Select template based on business type
            business_type = website_content.get("business_type", "general")
            template_id = self._select_template(business_type)
            
            # Create website in database
            website_data = {
                "client_id": client_id,
                "subdomain": subdomain,
                "template_id": template_id,
                "status": "draft",
                "seo_title": website_content.get("seo", {}).get("title", ""),
                "seo_description": website_content.get("seo", {}).get("description", "")
            }
            
            result = supabase.table("websites").insert(website_data).execute()
            website_id = result.data[0]["id"]
            
            # Create website content in database
            content_data = {
                "website_id": website_id,
                "version": 1,
                "is_current": True,
                "content": json.dumps(website_content),
                "content_type": "page",
                "path": "/"
            }
            
            supabase.table("website_content").insert(content_data).execute()
            
            return website_id
        except Exception as e:
            print(f"Error creating website: {e}")
            raise
    
    def _generate_subdomain(self, business_name: str) -> str:
        """
        Generate a subdomain from a business name.
        
        Args:
            business_name: Business name
            
        Returns:
            Subdomain
        """
        # Remove special characters and spaces
        subdomain = ''.join(c for c in business_name if c.isalnum() or c == ' ')
        subdomain = subdomain.lower().replace(' ', '-')
        
        # Add random suffix to ensure uniqueness
        import random
        import string
        suffix = ''.join(random.choices(string.digits, k=4))
        
        return f"{subdomain}-{suffix}"
    
    def _select_template(self, business_type: str) -> str:
        """
        Select a template based on business type.
        
        Args:
            business_type: Business type
            
        Returns:
            Template ID
        """
        # In a real implementation, this would query the database for templates
        # For now, we'll use mock template IDs
        template_mapping = {
            "restaurant": "template-restaurant-1",
            "retail": "template-retail-1",
            "fitness": "template-fitness-1",
            "beauty": "template-beauty-1",
            "web_development": "template-tech-1",
            "general": "template-general-1"
        }
        
        return template_mapping.get(business_type, "template-general-1")
    
    def _send_welcome_message(self, phone: str, name: str, website_id: str) -> None:
        """
        Send a welcome message to the client with website preview.
        
        Args:
            phone: Client's phone number
            name: Client's name
            website_id: Website ID
        """
        try:
            # Get website data
            result = supabase.table("websites").select("*").eq("id", website_id).execute()
            
            if not result.data or len(result.data) == 0:
                raise ValueError(f"Website with ID {website_id} not found")
            
            website = result.data[0]
            subdomain = website.get("subdomain", "")
            
            # Generate website URL
            website_url = f"https://{subdomain}.tuwebfacil.com"
            
            # Send welcome message
            message = f"""
            ¡Hola {name}! 👋

            ¡Tu sitio web ya está listo para que lo veas! 🎉

            Puedes acceder a tu sitio web en:
            {website_url}

            Este es un borrador inicial basado en tu perfil de Instagram. Puedes hacer cambios y personalizarlo a través de este chat de WhatsApp.

            Para comenzar a editar tu sitio, simplemente escribe "Editar sitio" y te guiaré a través del proceso.

            Si estás satisfecho con tu sitio web y deseas publicarlo, podemos configurar tu suscripción mensual.

            ¿Qué te gustaría hacer ahora?
            1️⃣ Editar mi sitio
            2️⃣ Configurar mi suscripción
            3️⃣ Hablar con un asesor
            """
            
            send_whatsapp_message(phone, message.strip())
        except Exception as e:
            print(f"Error sending welcome message: {e}")
            raise
    
    def _send_subscription_message(self, phone: str, name: str, subscription: Dict[str, Any]) -> None:
        """
        Send a subscription confirmation message to the client.
        
        Args:
            phone: Client's phone number
            name: Client's name
            subscription: Subscription data
        """
        try:
            # Get payment link
            payment_link = subscription.get("init_point", "https://tuwebfacil.com/pagos")
            
            # Send subscription message
            message = f"""
            ¡Hola {name}! 👋

            Tu suscripción a TuWebFacil ha sido creada con éxito. 🎉

            Para activar tu suscripción y publicar tu sitio web, por favor completa el pago a través del siguiente enlace:
            {payment_link}

            Una vez que hayas completado el pago, tu sitio web será publicado automáticamente y podrás comenzar a recibir visitas.

            Si tienes alguna pregunta, no dudes en contactarnos.

            ¡Gracias por confiar en TuWebFacil!
            """
            
            send_whatsapp_message(phone, message.strip())
        except Exception as e:
            print(f"Error sending subscription message: {e}")
            raise
    
    def _get_client_data(self, client_id: str) -> Dict[str, Any]:
        """
        Get client data from the database.
        
        Args:
            client_id: Client ID
            
        Returns:
            Client data
        """
        try:
            result = supabase.table("clients").select("*").eq("id", client_id).execute()
            
            if not result.data or len(result.data) == 0:
                raise ValueError(f"Client with ID {client_id} not found")
            
            return result.data[0]
        except Exception as e:
            print(f"Error getting client data: {e}")
            raise


# Main function to provision a client
def provision_client_from_instagram(phone: str, name: str, instagram_handle: str, email: Optional[str] = None) -> Dict[str, Any]:
    """
    Provision a client from their Instagram profile.
    
    Args:
        phone: Client's WhatsApp phone number
        name: Client's name
        instagram_handle: Client's Instagram handle
        email: Client's email address (optional)
        
    Returns:
        Dictionary with provisioning results
    """
    provisioner = ClientProvisioner()
    return provisioner.provision_client(phone, name, instagram_handle, email)


# Example usage
if __name__ == "__main__":
    # This is just for testing purposes
    try:
        result = provision_client_from_instagram(
            phone="5491134710787",
            name="Juan Pérez",
            instagram_handle="juanperez_design",
            email="juan@example.com"
        )
        print(f"Client provisioned successfully: {json.dumps(result, indent=2)}")
        
        # Set up subscription
        provisioner = ClientProvisioner()
        subscription_result = provisioner.setup_subscription(
            client_id=result["client_id"],
            plan_type="Plan Básico",
            email="juan@example.com"
        )
        print(f"Subscription set up successfully: {json.dumps(subscription_result, indent=2)}")
    except Exception as e:
        print(f"Error in example: {e}")