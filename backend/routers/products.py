from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models import Product, User
from backend.schemas import ProductCreate, ProductUpdate, ProductResponse
from backend.auth import get_current_user, require_role

router = APIRouter(prefix="/api/products", tags=["Products"])

@router.get("", response_model=List[ProductResponse])
def list_products(
    category: Optional[str] = None,
    stock_status: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: str = "asc",
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Enforce multi-tenancy by filtering by user's org_id
    query = db.query(Product).filter(Product.org_id == current_user.org_id)

    # Filtering
    if category:
        query = query.filter(Product.category.ilike(category))
    
    if search:
        query = query.filter(
            (Product.name.ilike(f"%{search}%")) | (Product.sku.ilike(f"%{search}%"))
        )

    # Fetch all matching products first to calculate in-memory stock status if needed,
    # or handle stock status filter at query level.
    # CRITICALLY_LOW: <= 10, HEALTHY: 11-100, OVERSTOCKED: > 100
    if stock_status:
        stock_status = stock_status.upper()
        if stock_status == "CRITICALLY_LOW":
            query = query.filter(Product.inventory_count <= 10)
        elif stock_status == "HEALTHY":
            query = query.filter((Product.inventory_count > 10) & (Product.inventory_count <= 100))
        elif stock_status == "OVERSTOCKED":
            query = query.filter(Product.inventory_count > 100)

    # Sorting
    if sort_by:
        # Check field to sort
        attr = getattr(Product, sort_by, None)
        if attr:
            if sort_order.lower() == "desc":
                query = query.order_by(attr.desc())
            else:
                query = query.order_by(attr.asc())
    else:
        query = query.order_by(Product.sku.asc())

    return query.all()


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    product_data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"]))
):
    # Check if SKU already exists for this org
    existing_product = db.query(Product).filter(
        Product.org_id == current_user.org_id,
        Product.sku == product_data.sku
    ).first()
    if existing_product:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SKU already exists in your organization catalog."
        )

    product = Product(
        org_id=current_user.org_id,
        sku=product_data.sku,
        name=product_data.name,
        category=product_data.category.lower(),
        current_price=product_data.current_price,
        cogs=product_data.cogs,
        inventory_count=product_data.inventory_count,
        margin_threshold=product_data.margin_threshold
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.org_id == current_user.org_id
    ).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or access denied."
        )
    return product


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: str,
    product_data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"]))
):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.org_id == current_user.org_id
    ).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or access denied."
        )

    # Apply updates
    update_dict = product_data.dict(exclude_unset=True)
    for key, value in update_dict.items():
        if key == "category" and value:
            value = value.lower()
        setattr(product, key, value)

    db.commit()
    db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_role(["ADMIN"]))
):
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.org_id == current_user.org_id
    ).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or access denied."
        )

    db.delete(product)
    db.commit()
    return None
