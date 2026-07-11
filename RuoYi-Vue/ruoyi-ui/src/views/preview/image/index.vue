<template>
  <div class="app-container">
    <el-card class="box-card">
      <div slot="header" class="card-header">
        <span><i class="el-icon-picture-outline"></i> 图片查询</span>
      </div>
      <el-form :model="form" label-width="80px">
        <el-form-item label="图片ID">
          <el-input
            v-model="form.id"
            placeholder="请输入图片ID（不超过32位）"
            maxlength="32"
            show-word-limit
            clearable
            style="width: 400px"
            @keyup.enter.native="handleQuery"
          />
          <el-button type="primary" icon="el-icon-search" @click="handleQuery" :loading="loading" style="margin-left: 10px">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="box-card" style="margin-top: 20px">
      <div slot="header" class="card-header">
        <span><i class="el-icon-picture"></i> 图片预览</span>
      </div>
      <div class="image-container" v-loading="loading" element-loading-text="正在加载图片...">
        <div v-if="imageUrl" class="image-wrapper">
          <el-image
            :src="imageUrl"
            fit="contain"
            :preview-src-list="[imageUrl]"
            style="max-width: 100%; max-height: 600px"
          />
        </div>
        <el-empty v-else description="请输入ID并点击查询获取图片" />
      </div>
    </el-card>
  </div>
</template>

<script>
import { queryPicture } from "@/api/preview/image"

export default {
  name: "ImagePreview",
  data() {
    return {
      form: {
        id: ""
      },
      imageUrl: "",
      loading: false,
      // 最近查询过的ID列表
      recentIds: []
    }
  },
  methods: {
      handleQuery() {
      const id = this.form.id
      if (!id) {
        this.$modal.msgWarning("请输入图片ID")
        return
      }
      if (id.length > 32) {
        this.$modal.msgWarning("ID长度不能超过32位")
        return
      }
      this.loading = true
      this.imageUrl = ""
      queryPicture(id).then((response) => {
        // 后端返回的是blob图片流，转换为url展示
        const blob = new Blob([response], { type: "image/jpeg" })
        this.imageUrl = URL.createObjectURL(blob)
        // 记录到最近查询列表（去重，最多保留10条）
        if (!this.recentIds.includes(id)) {
          this.recentIds.unshift(id)
          if (this.recentIds.length > 10) {
            this.recentIds.pop()
          }
        }
        this.$modal.msgSuccess("查询成功")
      }).catch((err) => {
        const message = err.message || err.msg || "查询图片失败"
        this.$modal.msgError(message)
      }).finally(() => {
        this.loading = false
      })
    }
  }
}
</script>

<style scoped>
.card-header {
  font-size: 16px;
  font-weight: bold;
}
.image-container {
  min-height: 300px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.image-wrapper {
  width: 100%;
  text-align: center;
}
</style>
