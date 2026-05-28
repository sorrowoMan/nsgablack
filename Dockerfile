FROM python:3.13-slim

WORKDIR /workspace

# 系统依赖：只需要 psycopg 的编译链
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python 依赖（分两层——不常变的先装，利用 Docker 缓存）
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 框架代码
COPY . .

# nsgablack 安装为可编辑包（因为你在开发中）
RUN pip install -e .

# 默认命令：没什么——这个 Image 是用来跑具体命令的，不是服务
CMD ["python", "-c", "print('nsgablack ready.')"]
