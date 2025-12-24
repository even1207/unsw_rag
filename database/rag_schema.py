"""
RAG 系统的完整数据库 Schema
包含 staff, publications, chunks, embeddings 等表
"""
from sqlalchemy import Column, String, Text, Integer, Float, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
# from pgvector.sqlalchemy import Vector  # 暂时注释掉，稍后安装 pgvector

Base = declarative_base()


class Staff(Base):
    """Staff 表 - 存储教职工基本信息"""
    __tablename__ = 'staff'

    # 使用 profile_url 作为主键，因为不是所有staff都有email
    profile_url = Column(String(512), primary_key=True)
    full_name = Column(String(255), nullable=False, index=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    role = Column(String(255))

    # 组织架构
    faculty = Column(String(255), index=True)
    school = Column(String(255), index=True)

    # 联系方式
    email = Column(String(255), index=True, nullable=True)
    phone = Column(String(50))
    photo_url = Column(String(512))

    # 个人简介
    summary = Column(Text)
    biography = Column(Text)
    research_text = Column(Text)

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    publications = relationship("Publication", back_populates="staff")
    chunks = relationship("Chunk", back_populates="staff")

    def __repr__(self):
        return f"<Staff(profile_url={self.profile_url}, name={self.full_name})>"


class Publication(Base):
    """Publication 表 - 存储论文信息"""
    __tablename__ = 'publications'

    # 主键：DOI 或生成的 hash
    id = Column(String(255), primary_key=True)

    # 基本信息
    title = Column(Text, nullable=False)  # 不加索引，因为有些title太长
    doi = Column(String(255), unique=True, index=True, nullable=True)
    publication_year = Column(Integer, index=True)
    pub_type = Column(String(100), index=True)  # journal, conference, etc.

    # 作者和来源
    authors = Column(JSON)  # [{name: "..."}]
    venue = Column(String(512))

    # Abstract
    abstract = Column(Text)
    abstract_source = Column(String(50), index=True)  # OpenAlex, Semantic Scholar, etc.

    # Metadata
    citations_count = Column(Integer, default=0)
    is_open_access = Column(Boolean, default=False)
    pdf_url = Column(String(512))
    concepts = Column(JSON)  # [{name: "...", score: 0.8}]

    # 标记
    has_doi = Column(Boolean, default=True, index=True)

    # 关联的 staff (使用 profile_url)
    staff_profile_url = Column(String(512), ForeignKey('staff.profile_url'), index=True)

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    staff = relationship("Staff", back_populates="publications")
    chunks = relationship("Chunk", back_populates="publication")
    publication_authors = relationship("PublicationAuthor", back_populates="publication", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Publication(id={self.id}, title={self.title[:50]})>"


class Chunk(Base):
    """Chunk 表 - 存储 RAG 的文本块"""
    __tablename__ = 'chunks'

    # 主键
    chunk_id = Column(String(255), primary_key=True)

    # Chunk 类型
    chunk_type = Column(String(50), nullable=False, index=True)
    # person_basic, person_biography, publication_title, publication_abstract, publication_keywords

    # 内容
    content = Column(Text, nullable=False)

    # Metadata (存储为 JSON，注意不能用 metadata，这是保留字)
    chunk_metadata = Column(JSON)

    # 关联
    staff_profile_url = Column(String(512), ForeignKey('staff.profile_url'), index=True)
    publication_id = Column(String(255), ForeignKey('publications.id'), nullable=True, index=True)

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    staff = relationship("Staff", back_populates="chunks")
    publication = relationship("Publication", back_populates="chunks")
    embedding = relationship("Embedding", back_populates="chunk", uselist=False)

    def __repr__(self):
        return f"<Chunk(id={self.chunk_id}, type={self.chunk_type})>"


class Embedding(Base):
    """Embedding 表 - 存储向量嵌入

    注意: 暂时使用 JSON 存储向量，等 pgvector 配置好后再迁移
    """
    __tablename__ = 'embeddings'

    # 主键
    chunk_id = Column(String(255), ForeignKey('chunks.chunk_id'), primary_key=True)

    # 向量 (暂时用 JSON 存储，后续迁移到 pgvector)
    # 假设使用 OpenAI text-embedding-ada-002 (1536 维)
    vector = Column(JSON, nullable=False)  # 存储为 JSON 数组

    # 嵌入模型信息
    model = Column(String(100), default='text-embedding-ada-002')

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    chunk = relationship("Chunk", back_populates="embedding")

    def __repr__(self):
        return f"<Embedding(chunk_id={self.chunk_id}, model={self.model})>"


class Author(Base):
    """Author 表 - 存储所有作者信息（包括UNSW和非UNSW）"""
    __tablename__ = 'authors'

    # 主键：使用自增ID
    id = Column(Integer, primary_key=True, autoincrement=True)

    # OpenAlex ID（如果有）
    openalex_id = Column(String(255), unique=True, index=True, nullable=True)

    # 基本信息
    name = Column(String(255), nullable=False, index=True)
    display_name = Column(String(255))  # OpenAlex的display_name

    # 机构信息
    last_known_institution = Column(String(512))  # 最后已知机构
    last_known_institution_id = Column(String(255))  # OpenAlex institution ID

    # ORCID
    orcid = Column(String(50), unique=True, index=True, nullable=True)

    # 统计信息（从OpenAlex）
    works_count = Column(Integer, default=0)  # 总论文数
    cited_by_count = Column(Integer, default=0)  # 总引用数
    h_index = Column(Integer, default=0)

    # 是否是UNSW staff（通过匹配确定）
    is_unsw_staff = Column(Boolean, default=False, index=True)
    unsw_staff_profile_url = Column(String(512), ForeignKey('staff.profile_url'), nullable=True)

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # 关系
    publications = relationship("PublicationAuthor", back_populates="author")
    staff = relationship("Staff", foreign_keys=[unsw_staff_profile_url])

    def __repr__(self):
        return f"<Author(id={self.id}, name={self.name}, openalex_id={self.openalex_id})>"


class PublicationAuthor(Base):
    """PublicationAuthor 关联表 - 论文和作者的多对多关系"""
    __tablename__ = 'publication_authors'

    # 复合主键
    publication_id = Column(String(255), ForeignKey('publications.id'), primary_key=True)
    author_id = Column(Integer, ForeignKey('authors.id'), primary_key=True)

    # 作者在论文中的位置（第几作者，从1开始）
    author_position = Column(Integer, nullable=False)

    # 是否是通讯作者
    is_corresponding = Column(Boolean, default=False)

    # 机构信息（作者在写这篇论文时的机构）
    institutions = Column(JSON)  # [{id: "...", display_name: "..."}]

    # 时间戳
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 关系
    publication = relationship("Publication", back_populates="publication_authors")
    author = relationship("Author", back_populates="publications")

    def __repr__(self):
        return f"<PublicationAuthor(pub={self.publication_id}, author={self.author_id}, pos={self.author_position})>"


def create_tables(engine):
    """创建所有表"""
    Base.metadata.create_all(engine)


def drop_tables(engine):
    """删除所有表"""
    Base.metadata.drop_all(engine)


def create_indexes(engine):
    """创建额外的索引（如向量索引）"""
    with engine.connect() as conn:
        # 为 pgvector 创建 HNSW 索引（用于快速相似度搜索）
        conn.execute("""
            CREATE INDEX IF NOT EXISTS embeddings_vector_idx
            ON embeddings
            USING hnsw (vector vector_cosine_ops)
        """)
        conn.commit()
