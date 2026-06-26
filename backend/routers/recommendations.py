from datetime import datetime
from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Product, Recommendation, PriceChangeAudit, Configuration, User
from backend.schemas import (
    RecommendationResponse,
    RecommendationReject,
    RecommendationModify,
    ConfigurationResponse,
    ConfigurationUpdate,
    AuditResponse
)
from backend.auth import get_current_user, require_role
from backend.services.orchestrator import PricingOrchestrator
from backend.services.compliance import ExecutionComplianceAgent

router = APIRouter(tags=["Recommendations & Compliance"])

@router.post("/api/recommendations/analyze/{product_id}", response_model=RecommendationResponse)
def trigger_analysis(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Enforce multi-tenancy
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.org_id == current_user.org_id
    ).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or access denied."
        )

    # 1. Run multi-agent pipeline
    orchestrator = PricingOrchestrator(db)
    try:
        strategy_output = orchestrator.run_pricing_pipeline(product.id)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent pipeline failed: {str(e)}"
        )

    # 2. Run compliance routing
    compliance_agent = ExecutionComplianceAgent(db)
    
    # Store old price to log changes if auto-executed
    old_price = product.current_price
    
    # Start a transaction savepoint / nested transaction to rollback specifically on storefront sync errors
    try:
        compliance_output = compliance_agent.process_recommendation(product, strategy_output)
    except RuntimeError as re:
        # Storefront failure triggers transaction rollback
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail=str(re)
        )

    # 3. Save recommendation
    # Convert Agent outputs to dict for JSON storage
    agent_rationale = {
        "market": strategy_output.market_analysis.dict(),
        "demand": strategy_output.demand_analysis.dict(),
        "inventory": strategy_output.inventory_analysis.dict(),
        "strategy_rationale": strategy_output.strategy_rationale,
        "compliance_logs": compliance_output.compliance_logs
    }

    # Convert decimals in dictionary to floats/strings to make it JSON serializable
    # (SQLite JSON field needs serializable types)
    def clean_decimal(obj):
        if isinstance(obj, dict):
            return {k: clean_decimal(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [clean_decimal(x) for x in obj]
        elif isinstance(obj, Decimal):
            return float(obj)
        return obj

    clean_rationale = clean_decimal(agent_rationale)

    recommendation = Recommendation(
        org_id=current_user.org_id,
        product_id=product.id,
        recommended_price=strategy_output.suggested_price,
        confidence_score=strategy_output.confidence_score,
        status="PENDING" if compliance_output.action_taken == "ROUTED_TO_REVIEW" else compliance_output.action_taken,
        agent_rationale=clean_rationale
    )
    db.add(recommendation)
    db.flush()

    # 4. If Auto-Executed, update product price and add audit trail in same transaction
    if compliance_output.action_taken == "AUTO_EXECUTED":
        product.current_price = strategy_output.suggested_price
        
        audit = PriceChangeAudit(
            org_id=current_user.org_id,
            product_id=product.id,
            recommendation_id=recommendation.id,
            old_price=old_price,
            new_price=strategy_output.suggested_price,
            changed_by=None,  # Null for auto
            change_type="AUTO"
        )
        db.add(audit)
        
    db.commit()
    db.refresh(recommendation)
    return recommendation


@router.get("/api/recommendations", response_model=List[RecommendationResponse])
def list_recommendations(
    status_filter: Optional[str] = "PENDING",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Recommendation).filter(Recommendation.org_id == current_user.org_id)
    if status_filter:
        query = query.filter(Recommendation.status == status_filter.upper())
    return query.order_by(Recommendation.suggested_at.desc()).all()


@router.get("/api/recommendations/{rec_id}", response_model=RecommendationResponse)
def get_recommendation(
    rec_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rec = db.query(Recommendation).filter(
        Recommendation.id == rec_id,
        Recommendation.org_id == current_user.org_id
    ).first()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recommendation not found or access denied."
        )
    return rec


@router.post("/api/recommendations/{rec_id}/approve", response_model=RecommendationResponse)
def approve_recommendation(
    rec_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rec = db.query(Recommendation).filter(
        Recommendation.id == rec_id,
        Recommendation.org_id == current_user.org_id
    ).first()
    if not rec or rec.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending recommendation not found."
        )

    product = db.query(Product).filter(Product.id == rec.product_id).first()
    old_price = product.current_price

    # Trigger Storefront Sync (will throw exception and trigger HTTP error on storefront fail)
    compliance_agent = ExecutionComplianceAgent(db)
    try:
        success, msg = compliance_agent.sync_to_storefront(product.id, rec.recommended_price)
        if not success:
            raise RuntimeError(msg)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail=f"Storefront sync failed: {str(e)}"
        )

    # Database updates inside single transaction
    rec.status = "APPROVED"
    rec.reviewed_at = datetime.utcnow()
    rec.reviewed_by = current_user.id
    
    product.current_price = rec.recommended_price
    
    audit = PriceChangeAudit(
        org_id=current_user.org_id,
        product_id=product.id,
        recommendation_id=rec.id,
        old_price=old_price,
        new_price=rec.recommended_price,
        changed_by=current_user.id,
        change_type="APPROVED"
    )
    db.add(audit)
    db.commit()
    db.refresh(rec)
    return rec


@router.post("/api/recommendations/{rec_id}/reject", response_model=RecommendationResponse)
def reject_recommendation(
    rec_id: str,
    reject_data: RecommendationReject,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rec = db.query(Recommendation).filter(
        Recommendation.id == rec_id,
        Recommendation.org_id == current_user.org_id
    ).first()
    if not rec or rec.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending recommendation not found."
        )

    rec.status = "REJECTED"
    rec.rejection_reason = reject_data.reason
    rec.reviewed_at = datetime.utcnow()
    rec.reviewed_by = current_user.id
    db.commit()
    db.refresh(rec)
    return rec


@router.post("/api/recommendations/{rec_id}/modify", response_model=RecommendationResponse)
def modify_recommendation(
    rec_id: str,
    modify_data: RecommendationModify,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    rec = db.query(Recommendation).filter(
        Recommendation.id == rec_id,
        Recommendation.org_id == current_user.org_id
    ).first()
    if not rec or rec.status != "PENDING":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pending recommendation not found."
        )

    product = db.query(Product).filter(Product.id == rec.product_id).first()
    
    # Enforce margin floor check for manual override
    config = db.query(Configuration).filter(Configuration.org_id == current_user.org_id).first()
    min_margin = product.margin_threshold
    if config and product.category in config.category_margin_floors:
        min_margin = config.category_margin_floors[product.category]

    margin_floor = product.cogs / Decimal(str(1 - min_margin))
    margin_floor = Decimal(f"{margin_floor:.2f}")

    if modify_data.price < margin_floor:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Manual override price {modify_data.price} breaches margin floor of {margin_floor}."
        )

    # Sync price to storefront
    compliance_agent = ExecutionComplianceAgent(db)
    try:
        success, msg = compliance_agent.sync_to_storefront(product.id, modify_data.price)
        if not success:
            raise RuntimeError(msg)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail=f"Storefront sync failed: {str(e)}"
        )

    old_price = product.current_price
    
    rec.status = "APPROVED"  # Indicate approved (with manual price)
    rec.reviewed_at = datetime.utcnow()
    rec.reviewed_by = current_user.id
    
    product.current_price = modify_data.price

    audit = PriceChangeAudit(
        org_id=current_user.org_id,
        product_id=product.id,
        recommendation_id=rec.id,
        old_price=old_price,
        new_price=modify_data.price,
        changed_by=current_user.id,
        change_type="MANUAL_OVERRIDE"
    )
    db.add(audit)
    db.commit()
    db.refresh(rec)
    return rec


@router.get("/api/config", response_model=ConfigurationResponse)
def get_config(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    config = db.query(Configuration).filter(Configuration.org_id == current_user.org_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found."
        )
    return config


@router.put("/api/config", response_model=ConfigurationResponse)
def update_config(
    config_data: ConfigurationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"]))
):
    config = db.query(Configuration).filter(Configuration.org_id == current_user.org_id).first()
    if not config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Configuration not found."
        )

    if config_data.auto_execute_threshold is not None:
        config.auto_execute_threshold = config_data.auto_execute_threshold
    if config_data.category_margin_floors is not None:
        config.category_margin_floors = config_data.category_margin_floors

    db.commit()
    db.refresh(config)
    return config


@router.get("/api/audits", response_model=List[AuditResponse])
def list_audits(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    return db.query(PriceChangeAudit).filter(
        PriceChangeAudit.org_id == current_user.org_id
    ).order_by(PriceChangeAudit.changed_at.desc()).all()
