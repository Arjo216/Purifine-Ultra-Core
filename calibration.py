import numpy as np

class AerosolPhysicsEngine:
    """
    Purifine Ultra Physics Core:
    Corrects Low-Cost Sensor data for Hygroscopic Growth (Humidity Swelling).
    """
    
    def __init__(self):
        # Kappa values (Hygroscopicity) for Indian environments
        self.KAPPA_MAP = {
            "traffic": 0.25,    # Soot (Hydrophobic)
            "industrial": 0.35, # Sulfates (Hygroscopic)
            "coastal": 0.45,    # Sea Salt (Very Hygroscopic - Mumbai/Chennai)
            "general": 0.30
        }

    def correct_pm25(self, raw_pm, humidity, env_type="general"):
        """
        Formula: PM_corrected = PM_raw / (1 + kappa * (RH/100-RH))
        """
        if raw_pm is None: return 0.0
        if humidity is None or humidity < 40: return raw_pm
        
        # Cap humidity at 99% to prevent math errors
        rh = min(humidity, 99.0)
        
        kappa = self.KAPPA_MAP.get(env_type, 0.3)
        
        # Calculate Volumetric Growth Factor
        growth_factor = 1 + kappa * (rh / (100 - rh))
        
        corrected_pm = raw_pm / growth_factor
        return round(corrected_pm, 2)

    def get_confidence_score(self, humidity):
        if humidity > 90: return "Low"     # Too wet, sensor unreliable
        if humidity > 75: return "Medium"
        return "High"