<template>
  <div class="app-container">
    <el-card>
      <div slot="header" class="card-header">
        <span><i class="el-icon-picture"></i> 图片浏览 - 数据集 {{ folder }}</span>
        <el-button style="float: right;" size="mini" @click="goBack">返回数据集列表</el-button>
      </div>

      <!-- 搜索栏 -->
      <el-form :inline="true" size="small" style="margin-bottom: 10px;">
        <el-form-item label="图片ID搜索">
          <el-input v-model="searchId" placeholder="输入图片ID关键词" clearable style="width: 200px;" @keyup.enter.native="handleSearch" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" icon="el-icon-search" @click="handleSearch">搜索</el-button>
          <el-button icon="el-icon-refresh" @click="resetSearch">重置</el-button>
        </el-form-item>
      </el-form>

      <!-- 图片网格 -->
      <div v-loading="loading">
        <div v-if="imageList.length > 0" class="image-grid">
          <div v-for="item in imageList" :key="item.id" class="image-grid-item" @click="viewDetail(item)">
            <el-image
              :src="getImageUrl(item.id)"
              fit="cover"
              class="image-thumb"
              lazy
            >
              <div slot="placeholder" class="image-slot">
                <i class="el-icon-loading"></i>
              </div>
              <div slot="error" class="image-slot">
                <i class="el-icon-picture-outline"></i>
              </div>
            </el-image>
            <div class="image-label">{{ item.id }}</div>
          </div>
        </div>
        <el-empty v-else-if="!loading" description="暂无图片数据" />
      </div>

      <!-- 分页 -->
      <el-pagination
        v-if="total > 0"
        background
        layout="total, sizes, prev, pager, next, jumper"
        :total="total"
        :page-sizes="[20, 40, 80, 120]"
        :page-size.sync="pageSize"
        :current-page.sync="pageNum"
        @size-change="fetchData"
        @current-change="fetchData"
        style="margin-top: 20px; text-align: center;"
      />
    </el-card>
  </div>
</template>

<script>
import { queryImageList, getRawImageUrl } from '@/api/visualization/dataset'

export default {
  name: 'ImageBrowser',
  data() {
    return {
      folder: '',
      imageList: [],
      total: 0,
      pageNum: 1,
      pageSize: 20,
      loading: false,
      searchId: ''
    }
  },
  created() {
    this.folder = this.$route.params.folder || '010'
  },
  mounted() {
    this.fetchData()
  },
  methods: {
    fetchData() {
      this.loading = true
      queryImageList(this.folder, this.pageNum, this.pageSize).then(response => {
        const data = response.data || {}
        this.imageList = data.rows || []
        this.total = data.total || 0
      }).catch(() => {
        this.$modal.msgError('获取图片列表失败')
      }).finally(() => {
        this.loading = false
      })
    },
    getImageUrl(id) {
      return getRawImageUrl(id)
    },
    handleSearch() {
      if (this.searchId) {
        // 使用搜索关键词过滤
        const filtered = this.imageList.filter(item => item.id.includes(this.searchId))
        if (filtered.length > 0) {
          this.imageList = filtered
          this.total = filtered.length
        } else {
          this.$modal.msgWarning('未找到匹配的图片')
        }
      } else {
        this.fetchData()
      }
    },
    resetSearch() {
      this.searchId = ''
      this.pageNum = 1
      this.fetchData()
    },
    viewDetail(item) {
      this.$router.push({ path: '/data-asset/detail/' + item.id })
    },
    goBack() {
      this.$router.push({ path: '/data-asset/dataset' })
    }
  }
}
</script>

<style scoped>
.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 16px;
}
.image-grid-item {
  border: 1px solid #ebeef5;
  border-radius: 6px;
  overflow: hidden;
  cursor: pointer;
  transition: all 0.3s;
  background: #fafafa;
}
.image-grid-item:hover {
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: translateY(-2px);
}
.image-thumb {
  width: 100%;
  height: 160px;
  display: block;
}
.image-slot {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  background: #f5f7fa;
  color: #c0c4cc;
  font-size: 24px;
}
.image-label {
  text-align: center;
  padding: 6px 4px;
  font-size: 12px;
  color: #606266;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
