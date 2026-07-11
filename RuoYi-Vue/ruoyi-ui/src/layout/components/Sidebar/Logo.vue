<template>
  <div class="sidebar-logo-container" :class="{'collapse':collapse}" :style="{ backgroundColor: sideTheme === 'theme-dark' && navType !== 3 ? variables.menuBackground : variables.menuLightBackground }">
    <transition name="sidebarLogoFade">
      <router-link v-if="collapse" key="collapse" class="sidebar-logo-link" to="/">
        <img v-if="logo" :src="logo" class="sidebar-logo" />
        <h1 v-else class="sidebar-title" :style="{ color: sideTheme === 'theme-dark' && navType !== 3 ? variables.logoTitleColor : variables.logoLightTitleColor }">{{ title }} </h1>
      </router-link>
      <router-link v-else key="expand" class="sidebar-logo-link" to="/">
        <img v-if="logo" :src="logo" class="sidebar-logo" />
        <div class="sidebar-title-group">
          <h1 class="sidebar-title" :style="{ color: sideTheme === 'theme-dark' && navType !== 3 ? variables.logoTitleColor : variables.logoLightTitleColor }">{{ title }} </h1>
          <span class="sidebar-subtitle">无人机智能检测系统</span>
        </div>
      </router-link>
    </transition>
  </div>
</template>

<script>
import logoImg from '@/assets/logo/logo.svg'
import variables from '@/assets/styles/variables.scss'

export default {
  name: 'SidebarLogo',
  props: {
    collapse: {
      type: Boolean,
      required: true
    }
  },
  computed: {
    variables() {
      return variables
    },
    sideTheme() {
      return this.$store.state.settings.sideTheme
    },
    navType() {
      return this.$store.state.settings.navType
    }
  },
  data() {
    return {
      title: process.env.VUE_APP_TITLE,
      logo: logoImg
    }
  }
}
</script>

<style lang="scss" scoped>
.sidebarLogoFade-enter-active {
  transition: opacity 1.5s;
}

.sidebarLogoFade-enter,
.sidebarLogoFade-leave-to {
  opacity: 0;
}

.sidebar-logo-container {
  position: relative;
  height: 64px;
  line-height: 64px;
  background: #0f1923;
  text-align: center;
  overflow: hidden;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);

  & .sidebar-logo-link {
    height: 100%;
    width: 100%;
    display: flex;
    align-items: center;
    justify-content: center;

    & .sidebar-logo {
      width: 32px;
      height: 32px;
      vertical-align: middle;
      margin-right: 10px;
      flex-shrink: 0;
    }

    & .sidebar-title-group {
      text-align: left;
      line-height: 1.3;

      & .sidebar-title {
        display: block;
        margin: 0;
        color: #fff;
        font-weight: 700;
        font-size: 15px;
        font-family: Avenir, Helvetica Neue, Arial, Helvetica, sans-serif;
        letter-spacing: 0.5px;
      }

      & .sidebar-subtitle {
        display: block;
        font-size: 10px;
        color: rgba(255, 255, 255, 0.55);
        letter-spacing: 1px;
      }
    }
  }

  &.collapse {
    height: 50px;
    line-height: 50px;

    .sidebar-logo {
      margin-right: 0px;
    }
  }
}
</style>
