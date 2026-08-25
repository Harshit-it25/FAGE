import pytest
import pandas as pd
import numpy as np
import os
import sys

# Add target path to python path to run locally
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.ml.preprocessing import FAGEPreprocessor

def test_leakage_features_are_dropped():
    # 25 semantic leakage features identified by dictionary
    semantic_leakage_features = [
        'F3899', 'F3900', 'F3901', 'F3902', 'F3903', 
        'F3904', 'F3905', 'F3906', 'F3907', 'F3908', 'F3909', 'F3910', 'F3911', 
        'F3912', 'F3913', 'F3914', 'F3915', 'F3919', 'F3920', 'F3921', 'F3922', 'F3923'
    ]
    
    # Create a dummy dataframe with these features + target
    data = {f: np.random.rand(100) for f in semantic_leakage_features}
    data['F3924'] = np.random.randint(0, 2, 100)
    data['F1'] = np.random.rand(100) # Valid feature
    
    df = pd.DataFrame(data)
    
    preprocessor = FAGEPreprocessor()
    df_transformed = preprocessor.fit_transform(X=df.drop(columns=['F3924']), y=df['F3924'])
    
    # Assert none of the leakage features made it through
    for f in semantic_leakage_features:
        assert f not in df_transformed.columns, f"Leakage feature {f} was not dropped!"
        
    # Assert the valid feature made it
    assert 'F1' in df_transformed.columns
    
def test_shap_compatibility():
    import pickle
    model_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models', 'production', 'model.pkl')
    shap_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'models', 'production', 'background_sample.pkl')
    
    if not (os.path.exists(model_path) and os.path.exists(shap_path)):
        pytest.skip("model artifacts not present — run train_models.py first")
        
    with open(model_path, 'rb') as f:
        model_artifact = pickle.load(f)
        
    with open(shap_path, 'rb') as f:
        bg_data = pickle.load(f)
        
    model_features = model_artifact['feature_names']
    shap_features = list(bg_data.columns)
    
    # Verify sizes match
    assert len(model_features) == len(shap_features), "Model features and SHAP sample features mismatch"
    
    # Verify no leakage feature exists in model features
    semantic_leakage_features = ['F3912', 'F3914']
    for f in semantic_leakage_features:
        assert f not in model_features

